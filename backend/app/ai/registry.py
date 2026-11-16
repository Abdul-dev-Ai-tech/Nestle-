"""Selects the detector from configuration. Swap models by changing .env, not code."""
import logging
import threading

from app.ai.base import DetectorUnavailable, PPEDetector
from app.core.config import get_settings
from app.models import PPE_ITEMS

log = logging.getLogger(__name__)
_lock = threading.Lock()
_detector: PPEDetector | None = None
_error: str | None = None


def get_detector() -> PPEDetector:
    """Return the configured detector or raise DetectorUnavailable."""
    global _detector, _error
    with _lock:
        if _detector is not None:
            return _detector
        s = get_settings()
        if s.AI_MODE == "disabled":
            raise DetectorUnavailable("AI detection is disabled (AI_MODE=disabled).")
        if s.AI_MODE == "simulation":
            from app.ai.simulated import SimulatedDetector
            _detector = SimulatedDetector()
        else:
            from app.ai.yolo import YoloDetector
            try:
                _detector = YoloDetector(s.YOLO_WEIGHTS, s.AI_CLASS_MAP, s.AI_DEVICE)
            except DetectorUnavailable as exc:
                _error = str(exc)
                log.error("YOLO detector unavailable: %s", exc)
                raise
        return _detector


def set_detector(detector: PPEDetector | None) -> None:
    """Override the detector (used by tests)."""
    global _detector, _error
    with _lock:
        _detector, _error = detector, None


def detector_info() -> dict:
    s = get_settings()
    try:
        return {**get_detector().info(), "available": True}
    except DetectorUnavailable as exc:
        return {"mode": s.AI_MODE, "available": False, "simulated": False, "error": str(exc),
                "model_name": None, "model_version": None,
                "classes": {i: {"status": "requires_training", "detail": "No trained model is loaded."}
                            for i in PPE_ITEMS}}
