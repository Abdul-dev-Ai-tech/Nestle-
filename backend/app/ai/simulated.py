"""Simulated detector for development and demonstrations.

It does NOT look at the image. Every result it returns is flagged `simulated=True`, is stored
with source="simulation", is labelled in the UI, and can never actuate real door hardware.
"""
import random

from app.ai.base import Detection, DetectionOutput, PPEDetector
from app.models import PPE_ITEMS


class SimulatedDetector(PPEDetector):
    name = "simulated-detector"
    version = "sim-1"
    simulated = True

    def __init__(self, miss_probability: float = 0.06, seed: int | None = None) -> None:
        self.miss_probability = miss_probability
        self._rng = random.Random(seed)

    def detect(self, image_bytes: bytes | None, force: str | None = None) -> DetectionOutput:
        forced_miss = self._rng.choice(PPE_ITEMS[:1] + PPE_ITEMS[1:3] + PPE_ITEMS[4:]) if force == "fail" else None
        detections = []
        for item in PPE_ITEMS:
            if force == "pass":
                ok = True
            elif force == "fail":
                ok = item != forced_miss
            else:
                ok = self._rng.random() > self.miss_probability
            conf = self._rng.uniform(0.88, 0.99) if ok else self._rng.uniform(0.70, 0.95)
            detections.append(Detection(item=item, detected=ok, confidence=round(conf, 3), bbox=None))
        return DetectionOutput(detections, self.name, self.version, simulated=True,
                               notes=["Simulated result — the image was not analysed."])

    def info(self) -> dict:
        return {"mode": "simulation", "model_name": self.name, "model_version": self.version, "simulated": True,
                "classes": {i: {"status": "simulated", "detail": "No model is analysing frames."} for i in PPE_ITEMS}}
