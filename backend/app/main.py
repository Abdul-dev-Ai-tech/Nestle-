"""FastAPI application entry point."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai.registry import detector_info
from app.api.deps import rate_limit
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
log = logging.getLogger("app")

if settings.SENTRY_DSN:  # optional error monitoring
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENV, send_default_pii=False)
    except ImportError:
        log.warning("SENTRY_DSN is set but sentry-sdk is not installed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    info = detector_info()
    log.info("Starting %s env=%s ai_mode=%s (available=%s) door_mode=%s", settings.APP_NAME, settings.ENV,
             settings.AI_MODE, info.get("available"), settings.DOOR_MODE)
    if settings.AI_MODE == "simulation":
        log.warning("AI_MODE=simulation: PPE results are SIMULATED and are not derived from camera frames.")
    yield


docs_enabled = not settings.is_production
app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan,
              docs_url="/api/docs" if docs_enabled else None, redoc_url=None,
              openapi_url="/api/openapi.json" if docs_enabled else None)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   allow_headers=["Content-Type", "X-CSRF-Token", "X-Requested-With"], max_age=600)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


@app.middleware("http")
async def security_and_logging(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # never leak internals to the client
        log.exception("Unhandled error id=%s %s %s", request_id, request.method, request.url.path)
        response = JSONResponse({"detail": "Internal server error", "request_id": request_id}, status_code=500)
    for k, v in SECURITY_HEADERS.items():
        if k == "Content-Security-Policy" and request.url.path.startswith("/api/docs"):
            continue
        response.headers.setdefault(k, v)
    if settings.COOKIE_SECURE:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/") and "stream" not in request.url.path:
        response.headers.setdefault("Cache-Control", "no-store")
    response.headers["X-Request-ID"] = request_id
    log.info("%s %s -> %s %.0fms id=%s", request.method, request.url.path, response.status_code,
             (time.perf_counter() - started) * 1000, request_id)
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
    first = errors[0] if errors else {"field": "", "message": "Invalid input"}
    detail = f"{first['field']}: {first['message']}" if first["field"] else first["message"]
    return JSONResponse({"detail": detail, "errors": errors}, status_code=422)


app.include_router(api_router, prefix="/api/v1", dependencies=[Depends(rate_limit)])


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}


@app.get("/api/health/ready", tags=["health"])
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Database is not reachable") from None
    return {"status": "ready"}
