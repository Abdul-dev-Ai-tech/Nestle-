"""Authorization is enforced by the API, independent of what the UI shows."""
from sqlalchemy import select

from app.models import Factory, Module
from tests.conftest import PASSWORD, make_client

NEW_EMP = {"employee_code": "NPK-99001", "full_name": "Rbac Test", "designation": "Operator"}


def test_viewer_cannot_modify_anything(viewer):
    assert viewer.post("/api/v1/employees", json=NEW_EMP).status_code == 403
    assert viewer.get("/api/v1/employees").status_code == 403           # no employees.view
    assert viewer.get("/api/v1/users").status_code == 403
    assert viewer.put("/api/v1/settings", json={"retention_days": 90}).status_code == 403
    assert viewer.post("/api/v1/access/doors/1/command", json={"command": "unlock", "reason": "testing"}).status_code == 403
    assert viewer.post("/api/v1/monitoring/check", data={"entry_point_id": 1}).status_code == 403
    assert viewer.get("/api/v1/reports/compliance?format=csv").status_code == 403  # view yes, export no
    assert viewer.get("/api/v1/reports/compliance").status_code == 200
    assert viewer.get("/api/v1/dashboard/summary").status_code == 200


def test_operator_can_monitor_but_not_override_or_manage(operator):
    assert operator.post("/api/v1/monitoring/check", data={"entry_point_id": 1}).status_code == 200
    assert operator.post("/api/v1/access/doors/1/command", json={"command": "unlock", "reason": "testing"}).status_code == 403
    assert operator.patch("/api/v1/violations/1", json={"status": "resolved"}).status_code == 403
    assert operator.post("/api/v1/cameras", json={"name": "Cam X", "type": "browser"}).status_code == 403


def test_manager_can_override_and_review_but_not_administer(manager):
    r = manager.post("/api/v1/access/doors/1/command", json={"command": "unlock", "reason": "Maintenance access"})
    assert r.status_code == 200 and r.json()["event"]["simulated"] is True
    assert manager.post("/api/v1/employees", json=NEW_EMP).status_code == 403
    assert manager.get("/api/v1/users").status_code == 403


def test_factory_admin_cannot_edit_permission_matrix_or_assign_super_admin(factory_admin):
    roles = factory_admin.get("/api/v1/roles").json()
    viewer = next(r for r in roles if r["name"] == "Viewer")
    superadmin = next(r for r in roles if r["name"] == "Super Admin")
    assert factory_admin.put(f"/api/v1/roles/{viewer['id']}/permissions", json={"permissions": []}).status_code == 403
    r = factory_admin.post("/api/v1/users", json={"email": "escalate@example.com", "full_name": "Escalate", "password": PASSWORD,
                                                  "role_ids": [superadmin["id"]]})
    assert r.status_code == 403


def test_permission_change_takes_effect_immediately(admin):
    roles = admin.get("/api/v1/roles").json()
    viewer_role = next(r for r in roles if r["name"] == "Viewer")
    c = make_client("viewer@example.com")
    assert c.get("/api/v1/employees").status_code == 403
    admin.put(f"/api/v1/roles/{viewer_role['id']}/permissions", json={"permissions": viewer_role["permissions"] + ["employees.view"]})
    assert c.get("/api/v1/employees").status_code == 200
    admin.put(f"/api/v1/roles/{viewer_role['id']}/permissions", json={"permissions": viewer_role["permissions"]})
    assert c.get("/api/v1/employees").status_code == 403


def test_super_admin_role_cannot_be_reduced(admin):
    sa = next(r for r in admin.get("/api/v1/roles").json() if r["name"] == "Super Admin")
    assert admin.put(f"/api/v1/roles/{sa['id']}/permissions", json={"permissions": []}).status_code == 400


def test_factory_data_isolation(admin, factory_admin, db):
    """A user restricted to factory 1 cannot read or write another factory's data."""
    r = admin.post("/api/v1/factories", json={"name": "Kabirwala Factory", "code": "PK-KBW", "timezone": "Asia/Karachi"})
    assert r.status_code == 201
    other = r.json()["id"]
    m = admin.post(f"/api/v1/modules?factory_id={other}", json={"name": "Dairy Intake", "code": "DIN", "first_entry_point": "Intake Gate"})
    assert m.status_code == 201
    e = admin.post(f"/api/v1/employees?factory_id={other}", json={"employee_code": "KBW-1", "full_name": "Other Factory Person"})
    assert e.status_code == 201
    # restricted user
    assert factory_admin.get(f"/api/v1/employees?factory_id={other}").status_code == 403
    assert factory_admin.get(f"/api/v1/employees/{e.json()['id']}").status_code == 404
    assert factory_admin.patch(f"/api/v1/modules/{m.json()['id']}", json={"name": "Hacked"}).status_code == 404
    assert factory_admin.get(f"/api/v1/dashboard/summary?factory_id={other}").status_code == 403
    assert [f["code"] for f in factory_admin.get("/api/v1/factories").json()] == ["PK-SKP"]
    listed = factory_admin.get("/api/v1/employees?page_size=100").json()["items"]
    assert all(x["factory_id"] == 1 for x in listed)
    # a module of another factory cannot be attached to an employee
    mine = factory_admin.get("/api/v1/employees?page_size=1").json()["items"][0]
    assert factory_admin.patch(f"/api/v1/employees/{mine['id']}", json={"module_id": m.json()["id"]}).status_code == 400
    assert db.scalar(select(Module.name).where(Module.id == m.json()["id"])) == "Dairy Intake"
    assert db.get(Factory, other) is not None
