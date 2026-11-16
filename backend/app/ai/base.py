"""Detector interface. Any model can be plugged in by implementing PPEDetector."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Detection:
    item: str                     # one of app.models.PPE_ITEMS
    detected: bool
    confidence: float             # 0..1 confidence of the reported state
    bbox: tuple[float, float, float, float] | None = None  # x, y, w, h normalised to 0..1


@dataclass
class DetectionOutput:
    detections: list[Detection]
    model_name: str
    model_version: str
    simulated: bool               # True when NO real model analysed the frame
    notes: list[str] = field(default_factory=list)

    def by_item(self) -> dict[str, Detection]:
        return {d.item: d for d in self.detections}


class DetectorUnavailable(RuntimeError):
    """Raised when no usable model is configured."""


class PPEDetector(ABC):
    name: str = "base"
    version: str = "0"
    simulated: bool = False

    @abstractmethod
    def detect(self, image_bytes: bytes | None) -> DetectionOutput:
        """Analyse one frame (JPEG/PNG bytes) and report every PPE item."""

    @abstractmethod
    def info(self) -> dict:
        """Describe the detector and the operational status of each class."""
