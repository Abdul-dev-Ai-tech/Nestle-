from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import DB, Config, CurrentUser, client_ip, get_session, require_ajax
from app.core.time import utcnow
from app.models import SessionRecord
from app.schemas.common import iso, user_out
from app.schemas.inputs import ChangePasswordIn, ForgotIn, LoginIn, ProfileIn, ResetIn
from app.security.passwords import hash_password, verify_password
from app.services import auth as svc
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _me(user, session: SessionRecord, settings) -> dict:
    return {"user": user_out(user), "permissions": sorted(user.permission_codes), "is_superuser": user.is_superuser,
            "session": {"id": session.id, "expires_at": iso(session.expires_at),
                        "idle_minutes": settings.SESSION_IDLE_MINUTES},
            "environment": settings.ENV}


@router.post("/login", dependencies=[Depends(require_ajax)])
def login(body: LoginIn, request: Request, response: Response, db: DB, settings: Config):
    ip = client_ip(request)
    user = svc.authenticate(db, body.email, body.password, ip)
    token, rec = svc.create_session(db, user, ip=ip, user_agent=request.headers.get("user-agent", ""))
    audit(db, user, "auth.login", "Signed in", ip=ip)
    db.commit()
    svc.set_session_cookies(response, token, rec)
    return _me(user, rec, settings)


@router.post("/logout")
def logout(response: Response, db: DB, request: Request, session: Annotated[SessionRecord, Depends(get_session)]):
    session.revoked_at = utcnow()
    audit(db, session.user, "auth.logout", "Signed out", ip=client_ip(request))
    db.commit()
    svc.clear_session_cookies(response)
    return {"ok": True}


@router.get("/me")
def me(user: CurrentUser, request: Request, settings: Config):
    return _me(user, request.state.session, settings)


@router.patch("/me")
def update_profile(body: ProfileIn, user: CurrentUser, db: DB, request: Request):
    user.full_name = body.full_name
    audit(db, user, "profile.update", "Updated own profile", ip=client_ip(request))
    db.commit()
    return user_out(user)


@router.post("/forgot-password", dependencies=[Depends(require_ajax)])
def forgot_password(body: ForgotIn, request: Request, db: DB, settings: Config):
    url = svc.start_password_reset(db, body.email, client_ip(request))
    db.commit()
    out = {"message": "If an account exists for this e-mail, a reset link has been sent."}
    if settings.DEV_RETURN_RESET_LINK and settings.ENV in ("development", "test") and url:
        out["dev_reset_url"] = url  # development convenience only; blocked by config validation elsewhere
    return out


@router.post("/reset-password", dependencies=[Depends(require_ajax)])
def reset_password(body: ResetIn, request: Request, db: DB):
    svc.complete_password_reset(db, body.token, body.new_password, client_ip(request))
    db.commit()
    return {"message": "Password updated. You can now sign in."}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, user: CurrentUser, request: Request, db: DB):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    if body.new_password == body.current_password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a password you have not just used.")
    svc.validate_new_password(body.new_password, user.email)
    user.password_hash, user.password_changed_at, user.must_change_password = hash_password(body.new_password), utcnow(), False
    revoked = svc.revoke_sessions(db, user.id, except_id=request.state.session.id)
    audit(db, user, "auth.password_changed", f"Password changed; {revoked} other session(s) revoked",
          ip=client_ip(request))
    db.commit()
    return {"message": "Password updated.", "other_sessions_revoked": revoked}


@router.get("/sessions")
def list_sessions(user: CurrentUser, request: Request, db: DB):
    rows = db.scalars(select(SessionRecord).where(SessionRecord.user_id == user.id, SessionRecord.revoked_at.is_(None),
                                                  SessionRecord.expires_at > utcnow())
                      .order_by(SessionRecord.last_seen_at.desc())).all()
    return [{"id": r.id, "ip": r.ip, "user_agent": r.user_agent, "created_at": iso(r.created_at),
             "last_seen_at": iso(r.last_seen_at), "current": r.id == request.state.session.id} for r in rows]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: int, user: CurrentUser, request: Request, db: DB):
    rec = db.get(SessionRecord, session_id)
    if rec is None or rec.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    rec.revoked_at = utcnow()
    audit(db, user, "auth.session_revoked", f"Revoked session {session_id}", ip=client_ip(request))
    db.commit()
    return {"ok": True}
