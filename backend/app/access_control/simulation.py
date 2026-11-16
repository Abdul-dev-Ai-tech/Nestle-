from app.access_control.base import DoorAdapter
from app.models import DoorController


class SimulatedDoorAdapter(DoorAdapter):
    """Default adapter: changes only the door state stored in the database."""

    is_simulation = True

    def unlock(self, door: DoorController, seconds: int) -> None:
        return None

    def lock(self, door: DoorController) -> None:
        return None

    def hold_open(self, door: DoorController) -> None:
        return None

    def health(self, door: DoorController) -> bool:
        return door.state != "fault"
