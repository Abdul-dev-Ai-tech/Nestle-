"""Backend camera access with OpenCV (USB webcams and RTSP / IP cameras).

Browsers cannot open RTSP streams or arbitrary USB devices on the server, so these sources are
read here and relayed to the UI as snapshots or an MJPEG stream.
Credentials are stored encrypted and injected into the URL only in memory, never logged.
"""
import logging
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from app.core.config import get_settings
from app.models import Camera
from app.security.crypto import decrypt_credentials

log = logging.getLogger(__name__)
BACKEND_TYPES = {"usb", "rtsp", "onvif"}
_URL_RE = re.compile(r"^(rtsp|rtsps|http|https)://[^\s@]+$", re.I)


class CameraError(RuntimeError):
    pass


@dataclass
class ProbeResult:
    ok: bool
    detail: str
    resolution: str = ""


def validate_source(cam_type: str, source: str) -> str:
    """Validate and normalise a camera source. Credentials inside URLs are rejected."""
    source = (source or "").strip()
    if cam_type == "browser":
        return ""
    if cam_type == "usb":
        if not re.fullmatch(r"\d{1,2}", source):
            raise ValueError("USB cameras use a device index such as 0 or 1")
        return source
    if cam_type in ("rtsp", "onvif"):
        if "@" in source:
            raise ValueError("Do not put a username or password in the stream URL; use the credentials fields")
        if not _URL_RE.match(source):
            raise ValueError("Enter a valid rtsp://, rtsps://, http:// or https:// stream address")
        return source
    raise ValueError("Unknown camera type")


def masked_source(camera: Camera) -> str:
    return camera.source


def _capture_target(camera: Camera):
    if camera.type == "usb":
        return int(camera.source or 0)
    creds = decrypt_credentials(camera.credentials_enc)
    if not creds or not creds[0]:
        return camera.source
    parts = urlsplit(camera.source)
    netloc = f"{quote(creds[0], safe='')}:{quote(creds[1], safe='')}@{parts.netloc}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _cv2():
    try:
        import cv2
        return cv2
    except ImportError as exc:  # pragma: no cover
        raise CameraError("OpenCV is not installed on the server") from exc


def open_capture(camera: Camera):
    if camera.type not in BACKEND_TYPES:
        raise CameraError("This camera is read in the browser, not on the server")
    cv2 = _cv2()
    timeout_ms = get_settings().CAMERA_OPEN_TIMEOUT_SECONDS * 1000
    if camera.type == "usb":
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(_capture_target(camera), backend)
    else:
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        cap = cv2.VideoCapture(_capture_target(camera), cv2.CAP_FFMPEG,
                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms, cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms])
    if not cap.isOpened():
        cap.release()
        raise CameraError("Could not open the camera. Check the address, credentials and network.")
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def encode_jpeg(frame, quality: int = 80) -> bytes:
    cv2 = _cv2()
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise CameraError("Could not encode the camera frame")
    return buf.tobytes()


def grab_frame(camera: Camera) -> bytes:
    """Open the camera, read one fresh frame and return it as JPEG bytes."""
    cap = open_capture(camera)
    try:
        frame = None
        for _ in range(4):  # discard buffered frames
            ok, frame = cap.read()
            if not ok:
                frame = None
                time.sleep(0.05)
        if frame is None:
            raise CameraError("The camera opened but returned no frames")
        return encode_jpeg(frame)
    finally:
        cap.release()


def probe(camera: Camera) -> ProbeResult:
    """Connection test used by the UI ("Test connection")."""
    if camera.type == "browser":
        return ProbeResult(True, "Browser cameras are tested on the device that opens the page.")
    try:
        cap = open_capture(camera)
    except CameraError as exc:
        return ProbeResult(False, str(exc))
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            return ProbeResult(False, "Connected, but no video frames were received")
        h, w = frame.shape[:2]
        return ProbeResult(True, "Camera is reachable and delivering video", f"{w}x{h}")
    finally:
        cap.release()
