"""Ultralytics YOLO detector.

Requires `pip install -r requirements-ai.txt` and trained weights (see ai_training/README.md).
A generic pretrained YOLO model does NOT know the five Nestlé PPE classes — it must be trained
and validated on site-specific images before any class is treated as operational.
"""
import io
import json
import logging
from pathlib import Path

from app.ai.base import Detection, DetectionOutput, DetectorUnavailable, PPEDetector
from app.models import PPE_ITEMS

log = logging.getLogger(__name__)


class YoloDetector(PPEDetector):
    name = "ultralytics-yolo"
    simulated = False

    def __init__(self, weights: str, class_map_path: str, device: str = "cpu", base_conf: float = 0.25) -> None:
        if not Path(weights).is_file():
            raise DetectorUnavailable(f"YOLO weights not found at '{weights}'. Train a model first.")
        try:
            from ultralytics import YOLO  # heavy import, kept lazy
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise DetectorUnavailable("ultralytics is not installed (pip install -r requirements-ai.txt)") from exc
        self._model = YOLO(weights)
        self._device = device
        self._base_conf = base_conf
        self.version = Path(weights).stem
        raw = json.loads(Path(class_map_path).read_text(encoding="utf-8"))
        self._map = {k: v for k, v in raw.items() if k in PPE_ITEMS}
        names = {str(n).lower() for n in self._model.names.values()}
        self._present = {i: [c for c in self._map.get(i, {}).get("present", []) if c.lower() in names]
                         for i in PPE_ITEMS}
        self._absent = {i: [c for c in self._map.get(i, {}).get("absent", []) if c.lower() in names]
                        for i in PPE_ITEMS}
        missing = [i for i in PPE_ITEMS if not self._present[i]]
        if missing:
            log.warning("YOLO model has no 'present' class mapped for: %s", ", ".join(missing))

    def detect(self, image_bytes: bytes | None) -> DetectionOutput:
        if not image_bytes:
            raise DetectorUnavailable("No image frame was supplied to the detector")
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        result = self._model.predict(image, conf=self._base_conf, device=self._device, verbose=False)[0]
        w, h = image.size
        best: dict[str, tuple[float, tuple]] = {}
        for box in result.boxes:
            cls = str(self._model.names[int(box.cls[0])]).lower()
            conf = float(box.conf[0])
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            if cls not in best or conf > best[cls][0]:
                best[cls] = (conf, (x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h))
        detections, notes = [], []
        for item in PPE_ITEMS:
            pres = max((best[c.lower()] for c in self._present[item] if c.lower() in best), default=None,
                       key=lambda t: t[0])
            absn = max((best[c.lower()] for c in self._absent[item] if c.lower() in best), default=None,
                       key=lambda t: t[0])
            if not self._present[item]:
                notes.append(f"{item}: no class in the loaded model — reported as not detected")
            if pres and (not absn or pres[0] >= absn[0]):
                detections.append(Detection(item, True, round(pres[0], 3), tuple(round(v, 4) for v in pres[1])))
            elif absn:
                detections.append(Detection(item, False, round(absn[0], 3), tuple(round(v, 4) for v in absn[1])))
            else:  # nothing seen: not detected, with no positive evidence
                detections.append(Detection(item, False, 0.0, None))
        return DetectionOutput(detections, self.name, self.version, simulated=False, notes=notes)

    def info(self) -> dict:
        classes = {}
        for item in PPE_ITEMS:
            if self._present[item]:
                classes[item] = {"status": "requires_validation",
                                 "detail": "Class present in the loaded model. Validate accuracy on site before "
                                           "relying on it.", "model_classes": self._present[item] + self._absent[item]}
            else:
                classes[item] = {"status": "requires_training", "detail": "No matching class in the loaded model."}
        return {"mode": "yolo", "model_name": self.name, "model_version": self.version, "simulated": False,
                "classes": classes}
