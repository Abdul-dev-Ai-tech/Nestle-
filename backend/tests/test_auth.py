from datetime import timedelta

from sqlalchemy import select

from app.core.time import utcnow
from app.models import SessionRecord, User
from tests.conftest import AJAX, PASSWORD, make_client

LOGIN = "/api/v1/auth/login"


def test_login_sets_httponly_cookie_and_returns_permissions(anon):
    r = anon.post(LOGIN, json={"email": "viewer@example.com", "password": PASSWORD}, headers=AJAX)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "nec_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    body = r.json()
    assert body["user"]["role"] == "Viewer" and "dashboard.view" in body["permissions"]
    assert "password" not in r.text.lower().replace("must_change_password", "")


def test_passwords_are_stored_as_argon2id(db):
    u = db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert u.password_hash.startswith("$argon2id$") and PASSWORD not in u.password_hash


def test_wrong_password_and_unknown_user_give_same_error(anon):
    a = anon.post(LOGIN, json={"email": "viewer@example.com", "password": "wrong-password"}, headers=AJAX)
    b = anon.post(LOGIN, json={"email": "nobody@example.com", "password": "wrong-password"}, headers=AJAX)
    assert a.status_code == b.status_code == 401 and a.json()["detail"] == b.json()["detail"]


def test_login_requires_ajax_header(anon):
    assert anon.post(LOGIN, json={"email": "viewer@example.com", "password": PASSWORD}).status_code == 403


def test_protected_api_requires_authentication(anon):
    assert anon.get("/api/v1/auth/me").status_code == 401
    assert anon.get("/api/v1/employees").status_code == 401
    assert anon.get("/api/v1/dashboard/summary").status_code == 401


def test_csrf_token_required_for_unsafe_requests(viewer):
    del viewer.headers["X-CSRF-Token"]
    assert viewer.post("/api/v1/auth/logout").status_code == 403
    viewer.headers["X-CSRF-Token"] = "not-the-token"
    assert viewer.post("/api/v1/auth/logout").status_code == 403
    assert viewer.get("/api/v1/auth/me").status_code == 200  # safe methods are unaffected


def test_logout_revokes_session(viewer):
    assert viewer.post("/api/v1/auth/logout").status_code == 200
    assert viewer.get("/api/v1/auth/me").status_code == 401


def test_account_lockout_after_repeated_failures(anon, admin):
    r = admin.post("/api/v1/users", json={"email": "lock.me@example.com", "full_name": "Lock Me", "password": PASSWORD,
                                          "role_ids": [_role_id(admin, "Viewer")], "factory_id": 1})
    assert r.status_code == 201
    for _ in range(5):
        assert anon.post(LOGIN, json={"email": "lock.me@example.com", "password": "bad"}, headers=AJAX).status_code == 401
    locked = anon.post(LOGIN, json={"email": "lock.me@example.com", "password": PASSWORD}, headers=AJAX)
    assert locked.status_code == 429 and "Too many failed attempts" in locked.json()["detail"]


def test_deactivated_account_cannot_sign_in_and_loses_sessions(admin):
    rid = _role_id(admin, "Viewer")
    uid = admin.post("/api/v1/users", json={"email": "leaver@example.com", "full_name": "Leaver", "password": PASSWORD,
                                            "role_ids": [rid], "factory_id": 1}).json()["id"]
    c = make_client("leaver@example.com")
    assert c.get("/api/v1/auth/me").status_code == 200
    assert admin.patch(f"/api/v1/users/{uid}", json={"is_active": False}).status_code == 200
    assert c.get("/api/v1/auth/me").status_code == 401
    r = make_client().post(LOGIN, json={"email": "leaver@example.com", "password": PASSWORD}, headers=AJAX)
    assert r.status_code == 403


def test_session_expires_when_idle(db):
    c = make_client("viewer@example.com")
    rec = db.scalars(select(SessionRecord).order_by(SessionRecord.id.desc())).first()
    rec.last_seen_at = utcnow() - timedelta(hours=3)
    db.commit()
    assert c.get("/api/v1/auth/me").status_code == 401


def test_password_reset_flow_is_single_use_and_revokes_sessions(admin, anon):
    rid = _role_id(admin, "Viewer")
    admin.post("/api/v1/users", json={"email": "reset.me@example.com", "full_name": "Reset Me", "password": PASSWORD,
                                      "role_ids": [rid], "factory_id": 1})
    old = make_client("reset.me@example.com")
    unknown = anon.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}, headers=AJAX)
    known = anon.post("/api/v1/auth/forgot-password", json={"email": "reset.me@example.com"}, headers=AJAX)
    assert unknown.status_code == known.status_code == 200
    assert unknown.json()["message"] == known.json()["message"] and "dev_reset_url" not in unknown.json()
    token = known.json()["dev_reset_url"].split("token=")[1]
    weak = anon.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"}, headers=AJAX)
    assert weak.status_code == 422
    new_pw = "Brand-New-Passw0rd!"
    assert anon.post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_pw}, headers=AJAX).status_code == 200
    assert anon.post("/api/v1/auth/reset-password", json={"token": token, "new_password": new_pw}, headers=AJAX).status_code == 400
    assert old.get("/api/v1/auth/me").status_code == 401  # other sessions revoked
    assert make_client("reset.me@example.com", new_pw).get("/api/v1/auth/me").status_code == 200


def test_change_password_checks_current_and_policy(admin):
    rid = _role_id(admin, "Viewer")
    admin.post("/api/v1/users", json={"email": "changer@example.com", "full_name": "Changer", "password": PASSWORD,
                                      "role_ids": [rid], "factory_id": 1})
    c = make_client("changer@example.com")
    assert c.post("/api/v1/auth/change-password", json={"current_password": "nope", "new_password": "Another-Passw0rd!"}).status_code == 400
    assert c.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "weak"}).status_code == 422
    assert c.post("/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": "Another-Passw0rd!"}).status_code == 200
    assert make_client("changer@example.com", "Another-Passw0rd!").get("/api/v1/auth/me").status_code == 200


def test_security_headers_present(anon):
    r = anon.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"


def _role_id(client, name):
    return next(r["id"] for r in client.get("/api/v1/roles").json() if r["name"] == name)
