"""Shared MJPEG relays: one reader thread per camera, any number of viewers, auto-reconnect."""
import logging
import threading
import time
from collections.abc import Iterator

from app.camera.sources import CameraError, encode_jpeg, open_capture
from app.models import Camera

log = logging.getLogger(__name__)
BOUNDARY = "frame"
IDLE_STOP_SECONDS = 15
MAX_FPS = 12


class _Reader(threading.Thread):
    def __init__(self, camera: Camera) -> None:
        super().__init__(daemon=True, name=f"camera-{camera.id}")
        self.camera = camera
        self.frame: bytes | None = None
        self.error: str | None = None
        self.last_access = time.monotonic()
        self.stop_flag = threading.Event()
        self.seq = 0

    def run(self) -> None:
        backoff = 1.0
        while not self.stop_flag.is_set():
            if time.monotonic() - self.last_access > IDLE_STOP_SECONDS:
                break
            try:
                cap = open_capture(self.camera)
            except CameraError as exc:
                self.error = str(exc)
                self.stop_flag.wait(backoff)
                backoff = min(backoff * 2, 30)  # exponential back-off while reconnecting
                continue
            backoff, self.error = 1.0, None
            try:
                while not self.stop_flag.is_set() and time.monotonic() - self.last_access <= IDLE_STOP_SECONDS:
                    ok, img = cap.read()
                    if not ok or img is None:
                        self.error = "Stream interrupted — reconnecting"
                        break
                    self.frame, self.seq = encode_jpeg(img, 70), self.seq + 1
                    time.sleep(1 / MAX_FPS)
            finally:
                cap.release()
        hub.discard(self.camera.id, self)


class StreamHub:
    def __init__(self) -> None:
        self._readers: dict[int, _Reader] = {}
        self._lock = threading.Lock()

    def reader(self, camera: Camera) -> _Reader:
        with self._lock:
            r = self._readers.get(camera.id)
            if r is None or not r.is_alive():
                r = _Reader(camera)
                self._readers[camera.id] = r
                r.start()
            r.last_access = time.monotonic()
            return r

    def discard(self, camera_id: int, reader: _Reader) -> None:
        with self._lock:
            if self._readers.get(camera_id) is reader:
                self._readers.pop(camera_id, None)

    def stop(self, camera_id: int) -> None:
        with self._lock:
            r = self._readers.pop(camera_id, None)
        if r:
            r.stop_flag.set()

    def latest_frame(self, camera: Camera, wait: float = 6.0) -> bytes | None:
        r = self.reader(camera)
        deadline = time.monotonic() + wait
        while r.frame is None and time.monotonic() < deadline and r.is_alive():
            time.sleep(0.1)
        return r.frame

    def mjpeg(self, camera: Camera) -> Iterator[bytes]:
        r = self.reader(camera)
        last = -1
        while True:
            r = self.reader(camera) if not r.is_alive() else r
            r.last_access = time.monotonic()
            if r.frame is not None and r.seq != last:
                last = r.seq
                yield (b"--" + BOUNDARY.encode() + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                       + str(len(r.frame)).encode() + b"\r\n\r\n" + r.frame + b"\r\n")
            time.sleep(1 / MAX_FPS)


hub = StreamHub()
