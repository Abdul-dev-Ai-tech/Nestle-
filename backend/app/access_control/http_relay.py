"""Template adapter for network relay boards that expose a simple HTTP API.

NOT verified against physical hardware. Before using it on site: confirm the relay model's API,
wire the lock so that power loss leaves the door in the state required by the fire/safety policy,
test in staging, and record an approval in the application (Access control > hardware approval).

door.config example (non-secret):
    {"base_url": "http://10.20.30.50", "unlock_path": "/relay/0?turn=on&timer={seconds}",
     "lock_path": "/relay/0?turn=off", "status_path": "/status", "timeout": 3}
"""
import httpx

from app.access_control.base import DoorAdapter, DoorAdapterError
from app.models import DoorController


class HttpRelayAdapter(DoorAdapter):
    is_simulation = False

    def _call(self, door: DoorController, key: str, **fmt) -> None:
        cfg = door.config or {}
        base, path = cfg.get("base_url"), cfg.get(key)
        if not base or not path:
            raise DoorAdapterError(f"Door controller is not configured ({key} missing)")
        try:
            r = httpx.get(base.rstrip("/") + path.format(**fmt), timeout=float(cfg.get("timeout", 3)))
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise DoorAdapterError(f"Door controller did not respond: {type(exc).__name__}") from exc

    def unlock(self, door: DoorController, seconds: int) -> None:
        self._call(door, "unlock_path", seconds=seconds)

    def lock(self, door: DoorController) -> None:
        self._call(door, "lock_path")

    def hold_open(self, door: DoorController) -> None:
        self._call(door, "unlock_path", seconds=0)

    def health(self, door: DoorController) -> bool:
        try:
            self._call(door, "status_path")
            return True
        except DoorAdapterError:
            return False
