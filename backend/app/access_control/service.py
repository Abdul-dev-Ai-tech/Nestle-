"""Access-control decisions and door actuation with safety interlocks.

SAFETY RULES (enforced here, covered by tests):
1. Simulation is the default. Real hardware needs DOOR_MODE=hardware AND HARDWARE_DOORS_ENABLED=true,
   a non-simulation adapter on the door, AND a recorded approval by an authorised user.
2. A simulated AI result can NEVER actuate real hardware.
3. A door only auto-opens on a PASS from the compliance engine. Anything else keeps it locked.
4. Any adapter error is fail-secure: the door is marked "fault", stays locked and an alert is raised.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.access_control.base import DoorAdapter, DoorAdapterError
from app.access_control.http_relay import HttpRelayAdapter
from app.access_control.simulation import SimulatedDoorAdapter
from app.core.config import get_settings
from app.core.time import utcnow
from app.models import AccessEvent, Alert, DoorController, EntryLog, User

log = logging.getLogger(__name__)
_ADAPTERS: dict[str, DoorAdapter] = {"simulation": SimulatedDoorAdapter(), "http_relay": HttpRelayAdapter()}


class DoorActionRefused(RuntimeError):
    pass


def register_adapter(name: str, adapter: DoorAdapter) -> None:
    _ADAPTERS[name] = adapter


def hardware_allowed(door: DoorController) -> bool:
    s = get_settings()
    return (s.DOOR_MODE == "hardware" and s.HARDWARE_DOORS_ENABLED and door.adapter != "simulation"
            and door.hardware_approved_at is not None and door.hardware_approved_by is not None)


def adapter_for(door: DoorController) -> DoorAdapter:
    """Real adapter only when every hardware condition holds; otherwise the simulator."""
    if hardware_allowed(door):
        return _ADAPTERS.get(door.adapter) or _ADAPTERS["simulation"]
    return _ADAPTERS["simulation"]


def refresh_state(door: DoorController) -> DoorController:
    """Timed unlocks re-lock automatically once their window has passed."""
    if door.state == "unlocked" and door.unlock_until and door.unlock_until <= utcnow():
        door.state, door.unlock_until = "locked", None
    return door


def _event(db: Session, door: DoorController, type_: str, *, simulated: bool, reason: str = "",
           entry: EntryLog | None = None, actor: User | None = None) -> AccessEvent:
    ev = AccessEvent(factory_id=door.factory_id, door_id=door.id, entry_log_id=entry.id if entry else None,
                     actor_user_id=actor.id if actor else None, type=type_, reason=reason[:300], simulated=simulated)
    db.add(ev)
    return ev


def _fault(db: Session, door: DoorController, exc: Exception) -> None:
    door.state, door.online, door.unlock_until = "fault", False, None
    _event(db, door, "fault", simulated=False, reason=str(exc))
    db.add(Alert(factory_id=door.factory_id, type="door_fault", severity="critical",
                 title=f"{door.name} — controller fault", detail="Door kept locked (fail-secure). " + str(exc)[:200],
                 ref_type="door", ref_id=door.id))
    log.error("Door %s fault: %s", door.id, exc)


def apply_entry_decision(db: Session, door: DoorController | None, entry: EntryLog, *, passed: bool,
                         detection_simulated: bool) -> dict:
    """Apply the automatic access decision for one entry. Returns a summary for the API."""
    if door is None:
        return {"door_id": None, "action": "none", "simulated": True, "message": "No door is linked to this entry point"}
    refresh_state(door)
    adapter = adapter_for(door)
    simulated = adapter.is_simulation
    if not passed:
        _event(db, door, "denied", simulated=simulated, reason="PPE check failed", entry=entry)
        return {"door_id": door.id, "action": "kept_locked", "simulated": simulated, "message": "Access denied"}
    if door.state == "fault":
        _event(db, door, "denied", simulated=simulated, reason="Door controller fault", entry=entry)
        return {"door_id": door.id, "action": "kept_locked", "simulated": simulated,
                "message": "PASS, but the door controller is in fault state"}
    if not door.auto_open:
        _event(db, door, "pass_no_auto_open", simulated=simulated, reason="Auto-open disabled", entry=entry)
        return {"door_id": door.id, "action": "none", "simulated": simulated,
                "message": "PASS — automatic opening is disabled for this door"}
    if detection_simulated and not simulated:  # rule 2
        _event(db, door, "blocked_simulated_result", simulated=False, entry=entry,
               reason="Simulated AI result must not actuate real hardware")
        return {"door_id": door.id, "action": "blocked", "simulated": False,
                "message": "Simulated AI result — real door was not actuated"}
    try:
        adapter.unlock(door, door.unlock_seconds)
    except DoorAdapterError as exc:
        _fault(db, door, exc)
        return {"door_id": door.id, "action": "fault", "simulated": simulated, "message": "Door controller fault"}
    door.state, door.unlock_until = "unlocked", utcnow() + timedelta(seconds=door.unlock_seconds)
    door.last_seen_at, door.online = utcnow(), True
    _event(db, door, "auto_unlock", simulated=simulated, reason="PPE check passed", entry=entry)
    return {"door_id": door.id, "action": "unlocked", "simulated": simulated,
            "message": f"Door released for {door.unlock_seconds} s" + (" (simulated)" if simulated else "")}


def manual_command(db: Session, door: DoorController, command: str, *, actor: User, reason: str) -> AccessEvent:
    """Manual override by an authorised user. `reason` is mandatory and audited by the caller."""
    refresh_state(door)
    if command not in ("unlock", "lock", "hold", "release"):
        raise DoorActionRefused("Unknown door command")
    if door.state == "fault" and command != "lock":
        raise DoorActionRefused("The door controller is in fault state")
    adapter = adapter_for(door)
    try:
        if command == "unlock":
            adapter.unlock(door, door.unlock_seconds)
            door.state, door.unlock_until = "unlocked", utcnow() + timedelta(seconds=door.unlock_seconds)
            type_ = "manual_unlock"
        elif command == "hold":
            adapter.hold_open(door)
            door.state, door.unlock_until = "held", None
            type_ = "hold_open"
        else:
            adapter.lock(door)
            type_ = "hold_release" if door.state == "held" else "manual_lock"
            door.state, door.unlock_until = "locked", None
    except DoorAdapterError as exc:
        _fault(db, door, exc)
        raise DoorActionRefused("The door controller did not respond; door kept locked") from exc
    door.last_seen_at = utcnow()
    return _event(db, door, type_, simulated=adapter.is_simulation, reason=reason, actor=actor)
