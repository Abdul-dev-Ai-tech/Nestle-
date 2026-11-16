"""Compliance decision engine.

Pure logic with no I/O: compares what the detector saw against what the module requires and
returns PASS/FAIL per item and overall. Kept separate from detection, storage and doors so it
can be tested exhaustively and audited.
"""
from dataclasses import asdict, dataclass

from app.ai.base import Detection
from app.models import PPE_ITEMS

ENGINE_VERSION = "1.0"


@dataclass(frozen=True)
class Requirement:
    required: bool
    min_confidence: float | None = None  # None -> use the default threshold


@dataclass(frozen=True)
class ItemResult:
    item: str
    required: bool
    detected: bool
    confidence: float
    threshold: float
    status: str  # pass | fail | not_required
    reason: str = ""
    bbox: tuple | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ComplianceResult:
    passed: bool
    decision: str  # granted | denied
    items: list[ItemResult]
    required_items: list[str]
    missing_items: list[str]
    threshold: float


def evaluate(detections: dict[str, Detection], requirements: dict[str, Requirement], *,
             default_threshold: float, beard_net_applicable: bool | None = None) -> ComplianceResult:
    """Evaluate one person.

    Rules:
    * An item passes only if it is required, detected, and confidence >= its threshold.
    * A required item the detector did not report at all FAILS (fail-closed).
    * Beard net is checked only when the module requires it AND it applies to the person;
      for an unidentified person (None) it is treated as applicable (conservative).
    * With no required items the result is PASS.
    """
    items: list[ItemResult] = []
    for item in PPE_ITEMS:
        req = requirements.get(item, Requirement(False))
        threshold = req.min_confidence if req.min_confidence is not None else default_threshold
        det = detections.get(item)
        required = req.required
        reason = ""
        if required and item == "beard_net" and beard_net_applicable is False:
            required, reason = False, "Not applicable to this employee"
        detected = bool(det and det.detected)
        confidence = float(det.confidence) if det else 0.0
        if not required:
            status = "not_required"
        elif det is None:
            status, reason = "fail", "No detection result for this item"
        elif not detected:
            status, reason = "fail", "Not detected"
        elif confidence < threshold:
            status, reason = "fail", f"Confidence {confidence:.0%} is below the {threshold:.0%} threshold"
        else:
            status = "pass"
        items.append(ItemResult(item, required, detected, round(confidence, 3), round(threshold, 3), status, reason,
                                det.bbox if det else None))
    required_items = [i.item for i in items if i.required]
    missing = [i.item for i in items if i.status == "fail"]
    passed = not missing
    return ComplianceResult(passed, "granted" if passed else "denied", items, required_items, missing,
                            round(default_threshold, 3))


def severity_for(missing: list[str], *, is_repeat: bool) -> str:
    if is_repeat:
        return "critical"
    return "high" if len(missing) >= 2 or "uniform" in missing else "medium"
