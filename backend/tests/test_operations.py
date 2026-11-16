"""Employees, monitoring pipeline, door safety, violations, cameras, uploads and reports."""

from sqlalchemy import select

from app.access_control import service as door_service
from app.access_control.base import DoorAdapter, DoorAdapterError
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import Camera, DoorController, EntryLog, Violation
from app.security.crypto import decrypt_credentials
from tests.conftest import jpeg_bytes


# ---------- employees ----------
def test_employee_crud_search_sort_pagination(admin):
    r = admin.post("/api/v1/employees", json={"employee_code": "npk-77001", "full_name": "Zed Tester", "designation": "Line Operator", "module_id": 1})
    assert r.status_code == 201 and r.json()["employee_code"] == "NPK-77001"
    eid = r.json()["id"]
    assert admin.post("/api/v1/employees", json={"employee_code": "NPK-77001", "full_name": "Duplicate"}).status_code == 409
    assert admin.post("/api/v1/employees", json={"employee_code": "bad code!", "full_name": "X Y"}).status_code == 422
    assert admin.post("/api/v1/employees", json={"employee_code": "NPK-77002", "full_name": "<script>alert(1)</script>"}).status_code == 422
    found = admin.get("/api/v1/employees?q=zed tester").json()
    assert found["total"] == 1 and found["items"][0]["id"] == eid
    p1 = admin.get("/api/v1/employees?page=1&page_size=5&sort=name&order=asc").json()
    p2 = admin.get("/api/v1/employees?page=2&page_size=5&sort=name&order=asc").json()
    names = [i["full_name"] for i in p1["items"] + p2["items"]]
    assert len(p1["items"]) == 5 and names == sorted(names) and p1["total"] > 10
    assert admin.patch(f"/api/v1/employees/{eid}", json={"status": "inactive"}).json()["status"] == "inactive"
    assert admin.get("/api/v1/employees?status=inactive&q=zed").json()["total"] == 1
    assert admin.delete(f"/api/v1/employees/{eid}").json()["result"] == "deleted"  # no history -> hard delete
    assert admin.get(f"/api/v1/employees/{eid}").status_code == 404


def test_employee_with_history_is_deactivated_not_deleted(admin, db):
    emp_id = db.scalar(select(EntryLog.employee_id).where(EntryLog.employee_id.is_not(None)).limit(1))
    assert admin.delete(f"/api/v1/employees/{emp_id}").json()["result"] == "deactivated"
    assert admin.get(f"/api/v1/employees/{emp_id}").json()["status"] == "inactive"
    assert admin.get(f"/api/v1/employees/{emp_id}/entries").json()["total"] > 0
    admin.patch(f"/api/v1/employees/{emp_id}", json={"status": "active"})


def test_photo_upload_validates_file_type_and_size(admin):
    eid = admin.get("/api/v1/employees?page_size=1").json()["items"][0]["id"]
    bad = admin.post(f"/api/v1/employees/{eid}/photo", files={"file": ("photo.jpg", b"<?php echo 1; ?>", "image/jpeg")})
    assert bad.status_code == 400
    big = admin.post(f"/api/v1/employees/{eid}/photo", files={"file": ("big.jpg", b"\xff\xd8" + b"0" * (6 * 1024 * 1024), "image/jpeg")})
    assert big.status_code == 413
    ok = admin.post(f"/api/v1/employees/{eid}/photo", files={"file": ("../../evil.jpg", jpeg_bytes(), "image/jpeg")})
    assert ok.status_code == 200
    img = admin.get(f"/api/v1/employees/{eid}/photo")
    assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"


# ---------- monitoring pipeline ----------
def _check(client, scenario, **extra):
    return client.post("/api/v1/monitoring/check", data={"entry_point_id": 1, "scenario": scenario, **extra},
                       files={"frame": ("frame.jpg", jpeg_bytes(), "image/jpeg")})


def test_pass_check_records_entry_and_simulated_unlock(admin, db):
    r = _check(admin, "pass")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["passed"] is True and body["decision"] == "granted" and body["detector"]["simulated"] is True
    assert body["door_result"]["action"] == "unlocked" and body["door_result"]["simulated"] is True
    entry = db.get(EntryLog, body["entry"]["id"])
    assert entry.source == "simulation" and entry.passed and len(entry.detections) == 5
    assert entry.compliance.passed and entry.violation is None and entry.evidence_path is None


def test_fail_check_creates_violation_alert_evidence_and_keeps_door_locked(admin, db):
    emp = admin.get("/api/v1/employees?status=active&page_size=1&module_id=1").json()["items"][0]
    r = _check(admin, "fail", employee_code=emp["employee_code"])
    body = r.json()
    assert r.status_code == 200 and body["passed"] is False and body["decision"] == "denied"
    assert body["missing_items"] and body["door_result"]["action"] == "kept_locked"
    v = db.get(Violation, body["violation_id"])
    assert v.status == "open" and v.employee_id == emp["id"] and v.missing_items == body["missing_items"]
    assert v.entry_log.evidence_path  # evidence stored for violations
    ev = admin.get(f"/api/v1/entries/{body['entry']['id']}/evidence")
    assert ev.status_code == 200 and ev.headers["content-type"] == "image/jpeg"
    alerts = admin.get("/api/v1/alerts?filter=unread").json()["items"]
    assert any(a["ref_type"] == "violation" and a["ref_id"] == v.id for a in alerts)
    door = db.scalar(select(DoorController).where(DoorController.entry_point_id == 1))
    db.refresh(door)
    assert door.state in ("locked", "unlocked")  # never opened by this failed check


def test_repeat_violations_are_flagged_critical(admin, db):
    emp = admin.get("/api/v1/employees?status=active&page_size=1&module_id=1&sort=code&order=desc").json()["items"][0]
    ids = [_check(admin, "fail", employee_code=emp["employee_code"]).json()["violation_id"] for _ in range(3)]
    last = db.get(Violation, ids[-1])
    assert last.is_repeat and last.severity == "critical"
    assert any(a["type"] == "repeat_violation" for a in admin.get("/api/v1/alerts?filter=critical").json()["items"])


def test_inactive_employee_and_invalid_frame_are_rejected(admin):
    eid = admin.post("/api/v1/employees", json={"employee_code": "NPK-88001", "full_name": "Inactive Person", "status": "inactive"}).json()["id"]
    assert _check(admin, "pass", employee_code="NPK-88001").status_code == 409
    assert _check(admin, "pass", employee_code="NPK-00000").status_code == 404
    bad = admin.post("/api/v1/monitoring/check", data={"entry_point_id": 1}, files={"frame": ("x.jpg", b"not an image", "image/jpeg")})
    assert bad.status_code == 400
    admin.delete(f"/api/v1/employees/{eid}")


def test_ppe_requirements_are_configurable_per_module(admin):
    mod = admin.get("/api/v1/modules").json()[0]
    rules = [{"item": i, "required": False} for i in mod["ppe"]]
    assert admin.put(f"/api/v1/modules/{mod['id']}/ppe", json={"rules": rules}).status_code == 200
    r = _check(admin, "fail")  # nothing is required -> must pass even though items are "missing"
    assert r.json()["passed"] is True
    rules = [{"item": i, "required": v["required"]} for i, v in mod["ppe"].items()]
    admin.put(f"/api/v1/modules/{mod['id']}/ppe", json={"rules": rules})


# ---------- door safety ----------
class _SpyAdapter(DoorAdapter):
    is_simulation = False

    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def unlock(self, door, seconds):
        self.calls.append("unlock")
        if self.fail:
            raise DoorAdapterError("relay timeout")

    def lock(self, door):
        self.calls.append("lock")

    def hold_open(self, door):
        self.calls.append("hold")

    def health(self, door):
        return True


def _hardware_door(db, monkeypatch, spy):
    s = get_settings()
    monkeypatch.setattr(s, "DOOR_MODE", "hardware")
    monkeypatch.setattr(s, "HARDWARE_DOORS_ENABLED", True)
    door_service.register_adapter("http_relay", spy)
    door = db.scalar(select(DoorController).where(DoorController.entry_point_id == 1))
    door.adapter, door.hardware_approved_by, door.hardware_approved_at, door.state = "http_relay", 1, utcnow(), "locked"
    db.commit()
    return door


def _restore(db, door):
    door.adapter, door.hardware_approved_by, door.hardware_approved_at, door.state, door.online = "simulation", None, None, "locked", True
    db.commit()


def test_simulated_ai_result_never_actuates_real_hardware(admin, db, monkeypatch):
    spy = _SpyAdapter()
    door = _hardware_door(db, monkeypatch, spy)
    try:
        body = _check(admin, "pass").json()
        assert body["passed"] is True and body["detector"]["simulated"] is True
        assert spy.calls == []  # the real adapter was NOT called
        assert body["door_result"]["action"] == "blocked"
    finally:
        _restore(db, door)


def test_hardware_needs_explicit_approval(admin, db, monkeypatch):
    spy = _SpyAdapter()
    door = _hardware_door(db, monkeypatch, spy)
    try:
        door.hardware_approved_at = None
        db.commit()
        assert door_service.adapter_for(door).is_simulation is True
        r = admin.post(f"/api/v1/access/doors/{door.id}/command", json={"command": "unlock", "reason": "Approval test"})
        assert r.status_code == 200 and r.json()["event"]["simulated"] is True and spy.calls == []
    finally:
        _restore(db, door)


def test_adapter_failure_is_fail_secure(admin, db, monkeypatch):
    spy = _SpyAdapter(fail=True)
    door = _hardware_door(db, monkeypatch, spy)
    try:
        r = admin.post(f"/api/v1/access/doors/{door.id}/command", json={"command": "unlock", "reason": "Fault test"})
        assert r.status_code == 409
        db.refresh(door)
        assert door.state == "fault" and spy.calls == ["unlock"]
        assert any(a["type"] == "door_fault" for a in admin.get("/api/v1/alerts?filter=critical").json()["items"])
    finally:
        _restore(db, door)


def test_manual_override_requires_reason_and_is_audited(admin):
    assert admin.post("/api/v1/access/doors/2/command", json={"command": "unlock", "reason": "x"}).status_code == 422
    r = admin.post("/api/v1/access/doors/2/command", json={"command": "hold", "reason": "Material movement"})
    assert r.status_code == 200 and r.json()["door"]["state"] == "held"
    assert admin.post("/api/v1/access/doors/2/command", json={"command": "release", "reason": "Movement finished"}).json()["door"]["state"] == "locked"
    log = admin.get("/api/v1/reports/audit?q=door.override").json()
    assert log["total"] >= 2 and "Material movement" in " ".join(x["detail"] for x in log["items"])


# ---------- violations ----------
def test_violation_filters_status_update_and_notes(manager):
    data = manager.get("/api/v1/violations?page_size=5").json()
    assert data["total"] > 0 and set(data["counts"]) == {"open", "under_review", "escalated", "resolved"}
    vid = data["items"][0]["id"]
    upd = manager.patch(f"/api/v1/violations/{vid}", json={"status": "resolved", "note": "Refresher training done"})
    assert upd.status_code == 200 and upd.json()["status"] == "resolved" and upd.json()["notes"]
    assert manager.post(f"/api/v1/violations/{vid}/notes", json={"text": "Follow-up scheduled"}).status_code == 201
    assert manager.patch(f"/api/v1/violations/{vid}", json={"status": "closed"}).status_code == 422
    only = manager.get("/api/v1/violations?status=resolved&page_size=50").json()["items"]
    assert only and all(v["status"] == "resolved" for v in only)
    item = data["items"][0]["missing_items"][0]
    filtered = manager.get(f"/api/v1/violations?item={item}&page_size=50").json()["items"]
    assert filtered and all(item in v["missing_items"] for v in filtered)


# ---------- cameras ----------
def test_camera_credentials_are_encrypted_and_never_returned(admin, db):
    bad = admin.post("/api/v1/cameras", json={"name": "Bad cam", "type": "rtsp", "source": "rtsp://user:secret@192.0.2.9/stream"})
    assert bad.status_code == 422  # credentials inside the URL are rejected
    r = admin.post("/api/v1/cameras", json={"name": "Dock camera", "type": "rtsp", "source": "rtsp://192.0.2.9:554/stream1",
                                            "username": "viewer", "password": "S3cret-Cam-Pass", "entry_point_id": 1})
    assert r.status_code == 201 and r.json()["has_credentials"] is True
    assert "S3cret-Cam-Pass" not in r.text and "credentials_enc" not in r.text
    cam = db.get(Camera, r.json()["id"])
    assert "S3cret-Cam-Pass" not in cam.credentials_enc and decrypt_credentials(cam.credentials_enc) == ("viewer", "S3cret-Cam-Pass")
    assert "S3cret-Cam-Pass" not in admin.get("/api/v1/cameras").text
    assert admin.post("/api/v1/cameras", json={"name": "USB cam", "type": "usb", "source": "abc"}).status_code == 422
    assert admin.delete(f"/api/v1/cameras/{r.json()['id']}").status_code == 200


def test_unreachable_camera_test_reports_offline(admin):
    cam = admin.post("/api/v1/cameras", json={"name": "Unreachable cam", "type": "usb", "source": "42"}).json()
    r = admin.post(f"/api/v1/cameras/{cam['id']}/test")
    assert r.status_code == 200 and r.json()["ok"] is False and r.json()["camera"]["status"] == "offline"
    admin.delete(f"/api/v1/cameras/{cam['id']}")


# ---------- dashboard & reports ----------
def test_dashboard_uses_database_records(admin, db):
    s = admin.get("/api/v1/dashboard/summary").json()
    assert len(s["daily"]) == 30 and s["today"]["entries"] >= 0 and len(s["doors"]) == 8
    assert sum(d["entries"] for d in s["daily"]) == sum(s["data_sources"].values())
    assert "sample" in s["data_sources"]
    one = admin.get("/api/v1/dashboard/summary?module_id=1").json()
    assert sum(d["entries"] for d in one["daily"]) < sum(d["entries"] for d in s["daily"])


def test_reports_and_csv_export(admin):
    for path in ("compliance", "compliance?granularity=week", "compliance?granularity=month", "shifts", "employees",
                 "modules", "ppe", "repeat-violations", "entries", "audit"):
        assert admin.get(f"/api/v1/reports/{path}").status_code == 200, path
    daily = admin.get("/api/v1/reports/compliance").json()
    assert daily["totals"]["entries"] == sum(r["entries"] for r in daily["series"])
    assert daily["totals"]["passed"] + daily["totals"]["failed"] == daily["totals"]["entries"]
    csv = admin.get("/api/v1/reports/employees?format=csv")
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert "attachment" in csv.headers["content-disposition"] and "Employee ID" in csv.text
    assert admin.get("/api/v1/reports/compliance?date_from=2020-13-45").status_code == 422


def test_sql_injection_attempts_are_harmless(admin):
    r = admin.get("/api/v1/employees", params={"q": "' OR 1=1; DROP TABLE employees; --"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert admin.get("/api/v1/employees").json()["total"] > 0
    assert admin.get("/api/v1/employees", params={"sort": "name; DROP TABLE users"}).status_code == 422


def test_settings_validation(admin):
    assert admin.put("/api/v1/settings", json={"confidence_threshold": 1.5}).status_code == 422
    assert admin.put("/api/v1/settings", json={"unknown_field": 1}).status_code == 422
    r = admin.put("/api/v1/settings", json={"confidence_threshold": 0.7, "retention_days": 180})
    assert r.status_code == 200 and r.json()["confidence_threshold"] == 0.7
    admin.put("/api/v1/settings", json={"confidence_threshold": 0.6, "retention_days": 365})
