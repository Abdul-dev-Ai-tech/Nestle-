"""The entry workflow: frame -> detection -> compliance -> records -> door decision -> alerts."""
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.access_control.service import apply_entry_decision
from app.ai.base import DetectionOutput
from app.ai.registry import get_detector
from app.core.config import get_settings
from app.core.time import shift_for, to_zone, utcnow
from app.models import (PPE_LABELS, Alert, Camera, ComplianceRecord, DetectionRecord, DoorController, Employee,
                        EntryLog, EntryPoint, Factory, FactorySetting, Violation)
from app.services import storage
from app.services.compliance import ENGINE_VERSION, ComplianceResult, Requirement, evaluate, severity_for


def get_factory_settings(db: Session, factory_id: int) -> FactorySetting:
    fs = db.scalar(select(FactorySetting).where(FactorySetting.factory_id == factory_id))
    if fs is None:
        fs = FactorySetting(factory_id=factory_id, confidence_threshold=get_settings().AI_DEFAULT_CONFIDENCE,
                            retention_days=get_settings().EVIDENCE_RETENTION_DAYS, notifications={})
        db.add(fs)
        db.flush()
    return fs


def requirements_for(entry_point: EntryPoint) -> dict[str, Requirement]:
    return {r.item: Requirement(r.required, r.min_confidence) for r in entry_point.module.ppe_requirements}


def labels(items: list[str]) -> str:
    return ", ".join(PPE_LABELS.get(i, i) for i in items)


def process_entry(db: Session, *, entry_point: EntryPoint, camera: Camera | None, employee: Employee | None,
                  image: bytes | None, operator_id: int | None, force: str | None = None) -> dict:
    """Run one complete entry check and persist everything. Commits the transaction."""
    module = entry_point.module
    factory = db.get(Factory, module.factory_id)
    fs = get_factory_settings(db, factory.id)

    # 1-2. detection
    detector = get_detector()  # raises DetectorUnavailable -> 503 at the API layer
    if detector.simulated:
        output: DetectionOutput = detector.detect(image, force=force)  # type: ignore[call-arg]
    else:
        output = detector.detect(image)

    # 3-5. compliance decision
    result: ComplianceResult = evaluate(
        output.by_item(), requirements_for(entry_point), default_threshold=fs.confidence_threshold,
        beard_net_applicable=employee.beard_net_applicable if employee else None)

    # 6. persist the entry
    now = utcnow()
    evidence = None
    if image and (fs.evidence_policy == "all" or not result.passed):
        evidence = storage.save_image(image, "evidence")
    entry = EntryLog(factory_id=factory.id, module_id=module.id, entry_point_id=entry_point.id,
                     camera_id=camera.id if camera else None, employee_id=employee.id if employee else None,
                     operator_id=operator_id, occurred_at=now, passed=result.passed, decision=result.decision,
                     missing_items=result.missing_items, shift=shift_for(to_zone(now, factory.timezone), factory.shifts),
                     source="simulation" if output.simulated else "live", evidence_path=evidence)
    db.add(entry)
    db.flush()
    for d in output.detections:
        db.add(DetectionRecord(entry_log_id=entry.id, item=d.item, detected=d.detected, confidence=d.confidence,
                               bbox=list(d.bbox) if d.bbox else None, model_name=output.model_name,
                               model_version=output.model_version, simulated=output.simulated))
    db.add(ComplianceRecord(entry_log_id=entry.id, required_items=result.required_items,
                            missing_items=result.missing_items, item_results=[i.to_dict() for i in result.items],
                            passed=result.passed, threshold=result.threshold, engine_version=ENGINE_VERSION))

    # 8. violation + alerts
    violation = None
    if not result.passed:
        violation = _record_violation(db, entry, employee, fs, entry_point)

    # 7. access-control decision
    door = db.scalar(select(DoorController).where(DoorController.entry_point_id == entry_point.id))
    door_result = apply_entry_decision(db, door, entry, passed=result.passed, detection_simulated=output.simulated)
    db.commit()
    return {"entry": entry, "result": result, "output": output, "door": door, "door_result": door_result,
            "violation": violation}


def _record_violation(db: Session, entry: EntryLog, employee: Employee | None, fs: FactorySetting,
                      entry_point: EntryPoint) -> Violation:
    is_repeat, count = False, 0
    if employee:
        since = entry.occurred_at - timedelta(days=fs.repeat_window_days)
        count = db.scalar(select(func.count(Violation.id)).where(Violation.employee_id == employee.id,
                                                                 Violation.created_at >= since)) or 0
        is_repeat = count + 1 >= fs.repeat_threshold
    v = Violation(factory_id=entry.factory_id, module_id=entry.module_id, entry_log_id=entry.id,
                  employee_id=employee.id if employee else None, missing_items=entry.missing_items,
                  severity=severity_for(entry.missing_items, is_repeat=is_repeat), status="open", is_repeat=is_repeat,
                  created_at=entry.occurred_at)
    db.add(v)
    db.flush()
    who = employee.full_name if employee else "Unidentified person"
    db.add(Alert(factory_id=entry.factory_id, type="ppe_violation", severity="high" if v.severity != "medium" else "medium",
                 title=f"{who} — entry denied", detail=f"Missing {labels(entry.missing_items)} at {entry_point.name}",
                 ref_type="violation", ref_id=v.id, created_at=entry.occurred_at))
    if is_repeat and employee:
        db.add(Alert(factory_id=entry.factory_id, type="repeat_violation", severity="critical",
                     title=f"{who} — {count + 1} violations in {fs.repeat_window_days} days",
                     detail="Repeat offender. Refresher hygiene training recommended.", ref_type="employee",
                     ref_id=employee.id, created_at=entry.occurred_at))
    return v
