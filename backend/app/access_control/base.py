"""Door controller adapter interface. One adapter per hardware family."""
from abc import ABC, abstractmethod

from app.models import DoorController


class DoorAdapterError(RuntimeError):
    pass


class DoorAdapter(ABC):
    #: True when the adapter never touches physical hardware.
    is_simulation: bool = False

    @abstractmethod
    def unlock(self, door: DoorController, seconds: int) -> None:
        """Release the door for `seconds`, then re-lock (the controller must re-lock by itself)."""

    @abstractmethod
    def lock(self, door: DoorController) -> None: ...

    @abstractmethod
    def hold_open(self, door: DoorController) -> None: ...

    @abstractmethod
    def health(self, door: DoorController) -> bool:
        """Return True when the controller answers."""
