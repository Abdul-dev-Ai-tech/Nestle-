"""Serialisers: explicit field lists so nothing sensitive (hashes, encrypted credentials) leaks."""
from app.access_control.service import hardware_allowed, refresh_state
from app.models import (PPE_ITEMS, PPE_LABELS, AccessEvent, Alert, Camera, DoorController, Employee, EntryLog,
                        EntryPoint, Factory, Module, Role, User, Violation)


def iso(dt):
    return dt.isoformat() if dt else None


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "is_active": u.is_active,
            "factory_id": u.factory_id, "roles": [{"id": r.id, "name": r.name} for r in u.roles],
            "role": u.primary_role, "last_login_at": iso(u.last_login_at), "created_at": iso(u.created_at),
            "must_change_password": u.must_change_password}


def role_out(r: Role, user_count: int = 0) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "is_system": r.is_system,
            "is_superuser": r.is_superuser, "rank": r.rank, "permissions": sorted(p.code for p in r.permissions),
            "user_count": user_count}


def factory_out(f: Factory) -> dict:
    return {"id": f.id, "name": f.name, "code": f.code, "address": f.address, "timezone": f.timezone,
            "shifts": f.shifts, "is_active": f.is_active}


def entry_point_out(e: EntryPoint) -> dict:
    return {"id": e.id, "name": e.name, "module_id": e.module_id, "is_active": e.is_active}


def module_out(m: Module) -> dict:
    ppe = {r.item: {"required": r.required, "min_confidence": r.min_confidence} for r in m.ppe_requirements}
    return {"id": m.id, "factory_id": m.factory_id, "name": m.name, "code": m.code, "description": m.description,
            "color": m.color, "is_active": m.is_active,
            "ppe": {i: ppe.get(i, {"required": False, "min_confidence": None}) for i in PPE_ITEMS},
            "entry_points": [entry_point_out(e) for e in m.entry_points]}


def employee_out(e: Employee) -> dict:
    return {"id": e.id, "factory_id": e.factory_id, "employee_code": e.employee_code, "full_name": e.full_name,
            "designation": e.designation, "shift": e.shift, "beard_net_applicable": e.beard_net_applicable,
            "status": e.status, "has_photo": bool(e.photo_path), "module_id": e.module_id,
            "module": {"id": e.module.id, "name": e.module.name, "color": e.module.color} if e.module else None,
            "department_id": e.department_id, "department": e.department.name if e.department else None,
            "created_at": iso(e.created_at)}


def employee_brief(e: Employee | None) -> dict | None:
    if e is None:
        return None
    return {"id": e.id, "employee_code": e.employee_code, "full_name": e.full_name, "designation": e.designation,
            "department": e.department.name if e.department else None, "shift": e.shift,
            "has_photo": bool(e.photo_path)}


def camera_out(c: Camera) -> dict:
    return {"id": c.id, "factory_id": c.factory_id, "name": c.name, "type": c.type, "source": c.source,
            "has_credentials": bool(c.credentials_enc), "is_active": c.is_active, "status": c.status,
            "last_seen_at": iso(c.last_seen_at), "last_error": c.last_error, "resolution": c.resolution,
            "entry_point_id": c.entry_point_id,
            "entry_point": c.entry_point.name if c.entry_point else None,
            "module_id": c.entry_point.module_id if c.entry_point else None}


def door_out(d: DoorController) -> dict:
    refresh_state(d)
    return {"id": d.id, "factory_id": d.factory_id, "name": d.name, "entry_point_id": d.entry_point_id,
            "entry_point": d.entry_point.name, "module_id": d.entry_point.module_id, "adapter": d.adapter,
            "config": d.config, "unlock_seconds": d.unlock_seconds, "fail_mode": d.fail_mode,
            "auto_open": d.auto_open, "state": d.state, "unlock_until": iso(d.unlock_until), "online": d.online,
            "last_seen_at": iso(d.last_seen_at), "hardware_active": hardware_allowed(d),
            "hardware_approved_at": iso(d.hardware_approved_at)}


def entry_out(e: EntryLog) -> dict:
    return {"id": e.id, "occurred_at": iso(e.occurred_at), "passed": e.passed, "decision": e.decision,
            "missing_items": e.missing_items, "missing_labels": [PPE_LABELS.get(i, i) for i in e.missing_items],
            "shift": e.shift, "source": e.source, "has_evidence": bool(e.evidence_path),
            "employee": employee_brief(e.employee),
            "module": {"id": e.module.id, "name": e.module.name, "color": e.module.color},
            "entry_point": e.entry_point.name if e.entry_point else None,
            "camera": e.camera.name if e.camera else None}


def violation_out(v: Violation, *, detail: bool = False) -> dict:
    e = v.entry_log
    out = {"id": v.id, "created_at": iso(v.created_at), "status": v.status, "severity": v.severity,
           "is_repeat": v.is_repeat, "missing_items": v.missing_items,
           "missing_labels": [PPE_LABELS.get(i, i) for i in v.missing_items], "employee": employee_brief(v.employee),
           "module": {"id": e.module.id, "name": e.module.name, "color": e.module.color},
           "entry_point": e.entry_point.name if e.entry_point else None,
           "camera": e.camera.name if e.camera else None, "entry_id": e.id, "source": e.source,
           "has_evidence": bool(e.evidence_path), "resolved_at": iso(v.resolved_at)}
    if detail:
        out["notes"] = [{"id": n.id, "author": n.author, "text": n.text, "created_at": iso(n.created_at)}
                        for n in v.notes]
        out["detections"] = [{"item": d.item, "label": PPE_LABELS.get(d.item, d.item), "detected": d.detected,
                              "confidence": d.confidence, "bbox": d.bbox, "simulated": d.simulated}
                             for d in e.detections]
        out["item_results"] = e.compliance.item_results if e.compliance else []
    return out


def alert_out(a: Alert) -> dict:
    return {"id": a.id, "type": a.type, "severity": a.severity, "title": a.title, "detail": a.detail,
            "ref_type": a.ref_type, "ref_id": a.ref_id, "created_at": iso(a.created_at), "read": a.read_at is not None,
            "acknowledged": a.acknowledged_at is not None}


def access_event_out(ev: AccessEvent) -> dict:
    return {"id": ev.id, "occurred_at": iso(ev.occurred_at), "type": ev.type, "reason": ev.reason,
            "simulated": ev.simulated, "door": ev.door.name, "door_id": ev.door_id,
            "actor": ev.actor.full_name if ev.actor else "System", "entry_id": ev.entry_log_id}


def page(items: list, total: int, page_no: int, size: int) -> dict:
    return {"items": items, "total": total, "page": page_no, "page_size": size}
