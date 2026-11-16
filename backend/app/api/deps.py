"""Shared FastAPI dependencies: database, authentication, CSRF, RBAC and factory scoping."""
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import get_db
from app.models import Factory, SessionRecord, User
from app.security.ratelimit import limiter
from app.security.tokens import constant_time_equal, hash_token

SESSION_COOKIE = "nec_session"
CSRF_COOKIE = "nec_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

DB = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]


def client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "")[:64]


def rate_limit(request: Request) -> None:
    settings = get_settings()
    is_auth = request.url.path.startswith("/api/v1/auth/") and request.method not in SAFE_METHODS
    limit = settings.AUTH_RATE_LIMIT_PER_MINUTE if is_auth else settings.RATE_LIMIT_PER_MINUTE
    if not limiter.allow(f"{'auth' if is_auth else 'api'}:{client_ip(request)}", limit):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please slow down.",
                            headers={"Retry-After": "60"})


def get_session(request: Request, db: DB) -> SessionRecord:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    settings = get_settings()
    rec = db.scalar(select(SessionRecord).where(SessionRecord.token_hash == hash_token(token)))
    now = utcnow()
    if (rec is None or rec.revoked_at is not None or rec.expires_at <= now
            or now - rec.last_seen_at > timedelta(minutes=settings.SESSION_IDLE_MINUTES)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please sign in again.")
    if not rec.user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is disabled")
    # CSRF: double-submit token bound to the server-side session, required on every unsafe request.
    if request.method not in SAFE_METHODS:
        sent = request.headers.get("x-csrf-token", "")
        if not sent or not constant_time_equal(sent, rec.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid")
    if (now - rec.last_seen_at).total_seconds() > 30:  # avoid a write on every request
        rec.last_seen_at = now
        db.commit()
    request.state.session = rec
    return rec


def get_current_user(session: Annotated[SessionRecord, Depends(get_session)]) -> User:
    return session.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*codes: str):
    """Dependency factory: the user must hold ALL listed permissions (enforced server-side)."""

    def checker(user: CurrentUser) -> User:
        held = user.permission_codes
        if not user.is_superuser and any(c not in held for c in codes):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return checker


def require_any(*codes: str):
    def checker(user: CurrentUser) -> User:
        if not user.is_superuser and not (user.permission_codes & set(codes)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to perform this action")
        return user

    return checker


def require_ajax(request: Request) -> None:
    """For unauthenticated unsafe endpoints (login, reset): a custom header cannot be sent
    cross-site without a CORS pre-flight, which the allow-list rejects."""
    if request.headers.get("x-requested-with", "").lower() != "xmlhttprequest":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing X-Requested-With header")


# ---------- factory scoping (data isolation between factories) ----------
def resolve_factory_id(db: Session, user: User, factory_id: int | None) -> int:
    """Return the factory the request operates on, enforcing the user's factory restriction."""
    if user.factory_id is not None:
        if factory_id is not None and factory_id != user.factory_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this factory")
        return user.factory_id
    if factory_id is None:
        first = db.scalar(select(Factory.id).where(Factory.is_active.is_(True)).order_by(Factory.id))
        if first is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No factory has been configured yet")
        return first
    if db.get(Factory, factory_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factory not found")
    return factory_id


def ensure_factory_access(user: User, factory_id: int) -> None:
    """Hide objects of other factories behind a 404."""
    if user.factory_id is not None and user.factory_id != factory_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
