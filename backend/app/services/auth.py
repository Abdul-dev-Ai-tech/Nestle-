"""Authentication: login protection, server-side sessions, password reset."""
from datetime import timedelta

from fastapi import HTTPException, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import CSRF_COOKIE, SESSION_COOKIE
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import LoginAttempt, PasswordResetToken, SessionRecord, User
from app.security.passwords import (hash_password, needs_rehash, password_policy_errors, verify_password)
from app.security.tokens import hash_token, new_token
from app.services.audit import audit
from app.services.mailer import send_mail

GENERIC_LOGIN_ERROR = "Incorrect e-mail or password."


def _recent_failures(db: Session, email: str) -> int:
    s = get_settings()
    since = utcnow() - timedelta(minutes=s.LOGIN_LOCK_MINUTES)
    last_ok = db.scalar(select(func.max(LoginAttempt.created_at)).where(
        LoginAttempt.email == email, LoginAttempt.success.is_(True), LoginAttempt.created_at >= since))
    q = select(func.count(LoginAttempt.id)).where(LoginAttempt.email == email, LoginAttempt.success.is_(False),
                                                  LoginAttempt.created_at >= (last_ok or since))
    return db.scalar(q) or 0


def authenticate(db: Session, email: str, password: str, ip: str) -> User:
    s = get_settings()
    email = email.lower().strip()
    if _recent_failures(db, email) >= s.LOGIN_MAX_ATTEMPTS:
        audit(db, None, "auth.locked", "Login blocked: too many failed attempts", ip=ip, email=email)
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed attempts. Try again in {s.LOGIN_LOCK_MINUTES} minutes.")
    user = db.scalar(select(User).where(User.email == email))
    ok = verify_password(password, user.password_hash if user else None)
    db.add(LoginAttempt(email=email, ip=ip, success=bool(ok and user and user.is_active)))
    if not ok or user is None:
        audit(db, None, "auth.login_failed", "Incorrect credentials", ip=ip, email=email)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR)
    if not user.is_active:
        audit(db, user, "auth.login_failed", "Account disabled", ip=ip)
        db.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is disabled. Contact your administrator.")
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utcnow()
    return user


def create_session(db: Session, user: User, *, ip: str, user_agent: str) -> tuple[str, SessionRecord]:
    s = get_settings()
    token = new_token(32)
    rec = SessionRecord(user_id=user.id, token_hash=hash_token(token), csrf_token=new_token(24), ip=ip,
                        user_agent=user_agent[:300], expires_at=utcnow() + timedelta(hours=s.SESSION_ABSOLUTE_HOURS))
    db.add(rec)
    return token, rec


def set_session_cookies(response: Response, token: str, rec: SessionRecord) -> None:
    s = get_settings()
    max_age = s.SESSION_ABSOLUTE_HOURS * 3600
    common = dict(secure=s.COOKIE_SECURE, samesite=s.COOKIE_SAMESITE, domain=s.COOKIE_DOMAIN, path="/", max_age=max_age)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, **common)
    # Readable by the SPA so it can echo it in the X-CSRF-Token header (double-submit, bound to the session).
    response.set_cookie(CSRF_COOKIE, rec.csrf_token, httponly=False, **common)


def clear_session_cookies(response: Response) -> None:
    s = get_settings()
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", domain=s.COOKIE_DOMAIN)


def revoke_sessions(db: Session, user_id: int, *, except_id: int | None = None) -> int:
    q = update(SessionRecord).where(SessionRecord.user_id == user_id, SessionRecord.revoked_at.is_(None))
    if except_id is not None:
        q = q.where(SessionRecord.id != except_id)
    return db.execute(q.values(revoked_at=utcnow())).rowcount or 0


def validate_new_password(password: str, email: str) -> None:
    errors = password_policy_errors(password, email=email)
    if errors:
        raise HTTPException(422, "Password needs: " + ", ".join(errors) + ".")


def start_password_reset(db: Session, email: str, ip: str) -> str | None:
    """Create a single-use reset token. Returns the reset URL (the caller decides whether to expose it)."""
    s = get_settings()
    user = db.scalar(select(User).where(User.email == email.lower().strip()))
    if user is None or not user.is_active:
        return None  # the API answers identically either way (no account enumeration)
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id,
                                                PasswordResetToken.used_at.is_(None)).values(used_at=utcnow()))
    token = new_token(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(token),
                              expires_at=utcnow() + timedelta(minutes=s.RESET_TOKEN_TTL_MINUTES)))
    audit(db, user, "auth.reset_requested", "Password reset link requested", ip=ip)
    url = f"{s.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    send_mail(user.email, "Reset your password",
              f"Hello {user.full_name},\n\nUse this link to choose a new password (valid for "
              f"{s.RESET_TOKEN_TTL_MINUTES} minutes):\n{url}\n\nIf you did not ask for this, ignore this e-mail.")
    return url


def complete_password_reset(db: Session, token: str, new_password: str, ip: str) -> None:
    rec = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token)))
    if rec is None or rec.used_at is not None or rec.expires_at <= utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired.")
    user = db.get(User, rec.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This reset link is invalid or has expired.")
    validate_new_password(new_password, user.email)
    user.password_hash, user.password_changed_at, user.must_change_password = hash_password(new_password), utcnow(), False
    rec.used_at = utcnow()
    revoke_sessions(db, user.id)  # sign out everywhere
    audit(db, user, "auth.password_reset", "Password reset completed; all sessions revoked", ip=ip)
