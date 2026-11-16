from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select

from app.ai.base import DetectorUnavailable
from app.ai.registry import detector_info
from app.api.deps import DB, Config, require
from app.api.v1.cameras import get_camera, record_status
from app.api.v1.org import get_entry_point
from app.camera.sources import BACKEND_TYPES, CameraError, grab_frame
from app.models import PPE_LABELS, Employee, User
from app.schemas.common import door_out, employee_brief, entry_out
from app.services import storage
from app.services.entry_pipeline import process_entry

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/status")
def ai_status(cfg: Config, _: Annotated[User, Depends(require("monitoring.view"))]):
    info = detector_info()
    return {**info, "labels": PPE_LABELS, "door_mode": cfg.DOOR_MODE,
            "can_force_scenario": bool(info.get("simulated")) and cfg.ENV in ("development", "test")}


@router.post("/check")
async def run_check(request: Request, db: DB, cfg: Config,
                    user: Annotated[User, Depends(require("monitoring.operate"))],
                    entry_point_id: Annotated[int, Form()],
                    camera_id: Annotated[int | None, Form()] = None,
                    employee_code: Annotated[str | None, Form(max_length=20)] = None,
                    scenario: Annotated[Literal["random", "pass", "fail"], Form()] = "random",
                    frame: UploadFile | None = File(default=None)):
    """Run one PPE entry check.

    The frame comes either from the browser (multipart `frame`, e.g. a webcam/mobile capture) or,
    for USB/RTSP cameras, is grabbed by the server from `camera_id`.
    """
    ep = get_entry_point(db, entry_point_id, user)
    if not ep.is_active or not ep.module.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "This entry point or its module is not active")
    camera = get_camera(db, camera_id, user) if camera_id else None
    employee = None
    if employee_code:
        employee = db.scalar(select(Employee).where(Employee.factory_id == ep.module.factory_id,
                                                    Employee.employee_code == employee_code.upper().strip()))
        if employee is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No employee with this code")
        if employee.status != "active":
            raise HTTPException(status.HTTP_409_CONFLICT, "This employee is inactive and may not request entry")

    image: bytes | None = None
    if frame is not None:
        image = await storage.read_upload(frame)
        storage.validate_image(image)
    elif camera is not None and camera.type in BACKEND_TYPES:
        try:
            image = await run_in_threadpool(grab_frame, camera)
            record_status(db, camera, True, "")
        except CameraError as exc:
            record_status(db, camera, False, str(exc))
            db.commit()
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not read the camera: {exc}") from None

    info = detector_info()
    if not info.get("simulated") and image is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A camera frame is required to run detection")
    force = scenario if scenario != "random" and info.get("simulated") and cfg.ENV in ("development", "test") else None
    try:
        out = await run_in_threadpool(lambda: process_entry(db, entry_point=ep, camera=camera, employee=employee,
                                                            image=image, operator_id=user.id, force=force))
    except DetectorUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"AI detection is not available: {exc}") from None

    entry, result, output = out["entry"], out["result"], out["output"]
    return {
        "entry": entry_out(entry), "passed": result.passed, "decision": result.decision,
        "items": [{**i.to_dict(), "label": PPE_LABELS[i.item]} for i in result.items],
        "missing_items": result.missing_items, "missing_labels": [PPE_LABELS[i] for i in result.missing_items],
        "threshold": result.threshold, "employee": employee_brief(employee),
        "detector": {"model_name": output.model_name, "model_version": output.model_version,
                     "simulated": output.simulated, "notes": output.notes},
        "door": door_out(out["door"]) if out["door"] else None, "door_result": out["door_result"],
        "violation_id": out["violation"].id if out["violation"] else None,
    }
