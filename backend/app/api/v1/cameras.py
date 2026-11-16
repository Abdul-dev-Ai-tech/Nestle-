from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select

from app.api.deps import DB, client_ip, ensure_factory_access, require, resolve_factory_id
from app.api.v1.org import get_entry_point
from app.camera import onvif
from app.camera.sources import BACKEND_TYPES, CameraError, grab_frame, probe, validate_source
from app.camera.stream import BOUNDARY, hub
from app.core.time import utcnow
from app.models import Alert, Camera, User
from app.schemas.common import camera_out
from app.schemas.inputs import CameraIn
from app.security.crypto import CredentialKeyMissing, encrypt_credentials
from app.services.audit import audit

router = APIRouter(prefix="/cameras", tags=["cameras"])
View = Annotated[User, Depends(require("cameras.view"))]
Manage = Annotated[User, Depends(require("cameras.manage"))]


def get_camera(db, camera_id: int, user: User) -> Camera:
    c = db.get(Camera, camera_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Camera not found")
    ensure_factory_access(user, c.factory_id)
    return c


def _apply(db, cam: Camera, body: CameraIn, user: User) -> None:
    try:
        cam.source = validate_source(body.type, body.source)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    cam.name, cam.type, cam.is_active = body.name, body.type, body.is_active
    if body.entry_point_id is not None:
        ep = get_entry_point(db, body.entry_point_id, user)
        if ep.module.factory_id != cam.factory_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Entry point belongs to another factory")
    cam.entry_point_id = body.entry_point_id
    if body.clear_credentials or body.type in ("browser", "usb"):
        cam.credentials_enc = None
    elif body.username is not None and body.password is not None and body.username != "":
        try:
            cam.credentials_enc = encrypt_credentials(body.username, body.password)
        except CredentialKeyMissing:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                                "Camera credentials cannot be stored: CAMERA_CREDENTIALS_KEY is not configured") from None


@router.get("")
def list_cameras(db: DB, user: Annotated[User, Depends(require("dashboard.view"))], factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    return [camera_out(c) for c in db.scalars(select(Camera).where(Camera.factory_id == fid).order_by(Camera.id)).all()]


@router.post("", status_code=201)
def create_camera(body: CameraIn, request: Request, db: DB, user: Manage, factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    cam = Camera(factory_id=fid, name=body.name, type=body.type)
    _apply(db, cam, body, user)
    db.add(cam)
    audit(db, user, "camera.create", f"Added camera {cam.name} ({cam.type})", ip=client_ip(request), factory_id=fid)
    db.commit()
    db.refresh(cam)
    return camera_out(cam)


@router.put("/{camera_id}")
def update_camera(camera_id: int, body: CameraIn, request: Request, db: DB, user: Manage):
    cam = get_camera(db, camera_id, user)
    _apply(db, cam, body, user)
    hub.stop(cam.id)
    cam.status, cam.last_error = "unknown", ""
    audit(db, user, "camera.update", f"Updated camera {cam.name}" + (" (credentials changed)" if body.password else ""),
          ip=client_ip(request), factory_id=cam.factory_id)
    db.commit()
    db.refresh(cam)
    return camera_out(cam)


@router.delete("/{camera_id}")
def delete_camera(camera_id: int, request: Request, db: DB, user: Manage):
    cam = get_camera(db, camera_id, user)
    hub.stop(cam.id)
    db.delete(cam)
    audit(db, user, "camera.delete", f"Removed camera {cam.name}", ip=client_ip(request), factory_id=cam.factory_id)
    db.commit()
    return {"ok": True}


def record_status(db, cam: Camera, ok: bool, detail: str, resolution: str = "") -> None:
    was = cam.status
    cam.status, cam.last_error = ("online", "") if ok else ("offline", detail[:250])
    if ok:
        cam.last_seen_at = utcnow()
        cam.resolution = resolution or cam.resolution
    elif was != "offline":
        db.add(Alert(factory_id=cam.factory_id, type="camera_offline", severity="high", title=f"{cam.name} is offline",
                     detail=detail[:300], ref_type="camera", ref_id=cam.id))


@router.post("/{camera_id}/test")
async def test_camera(camera_id: int, request: Request, db: DB, user: Manage):
    cam = get_camera(db, camera_id, user)
    result = await run_in_threadpool(probe, cam)
    if cam.type in BACKEND_TYPES:
        record_status(db, cam, result.ok, result.detail, result.resolution)
    audit(db, user, "camera.test", f"{cam.name}: {'ok' if result.ok else 'failed'}", ip=client_ip(request),
          factory_id=cam.factory_id)
    db.commit()
    return {"ok": result.ok, "detail": result.detail, "resolution": result.resolution, "camera": camera_out(cam)}


@router.get("/{camera_id}/snapshot")
async def snapshot(camera_id: int, db: DB, user: View):
    cam = get_camera(db, camera_id, user)
    try:
        data = await run_in_threadpool(grab_frame, cam)
    except CameraError as exc:
        record_status(db, cam, False, str(exc))
        db.commit()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None
    record_status(db, cam, True, "")
    db.commit()
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{camera_id}/stream")
def stream(camera_id: int, db: DB, user: View):
    """MJPEG relay of a USB/RTSP camera, viewable in an <img> tag (cookie-authenticated)."""
    cam = get_camera(db, camera_id, user)
    if cam.type not in BACKEND_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Browser cameras are previewed on the device itself")
    if not cam.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Camera is disabled")
    db.expunge(cam)  # detached copy for the reader thread
    return StreamingResponse(hub.mjpeg(cam), media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
                             headers={"Cache-Control": "no-store"})


@router.post("/discover")
async def discover(user: Manage):
    """ONVIF WS-Discovery on the server's local network segment."""
    devices = await run_in_threadpool(onvif.discover)
    return {"devices": devices,
            "note": "Only devices on the same network segment as the server answer. Enter the RTSP address and "
                    "credentials for a found device to add it."}
