# AI model: status, training and validation

## Honest status

**No trained PPE model is included, and none of the five classes is operational.** A generic pretrained
YOLO model (trained on COCO) knows "person" but not *hair cap*, *beard net*, *factory uniform* or *safety
shoes*; public PPE datasets mostly cover construction helmets and vests, not food-factory hygiene wear.
Reliable detection needs a model trained on images from **your** entry points with **your** PPE.

| Class | Status today | To become operational |
|---|---|---|
| Uniform | Requires training | Dataset + training + validation |
| Hair cap | Requires training | same |
| Face mask | Requires training (public mask datasets can help as a starting point) | same |
| Beard net | Requires training (hard: small, similar to a mask) | same, with extra close-up images |
| Safety shoes | Requires training (needs a camera that sees the feet) | same; consider a second, low camera |

Until then the app runs with `AI_MODE=simulation` (development; clearly labelled, never opens real doors)
or `AI_MODE=disabled`. Production refuses `simulation`.

## What is implemented

* `app/ai/base.py` — `PPEDetector` interface (`detect(image) → detections with confidence and box`).
* `app/ai/yolo.py` — Ultralytics YOLO detector; maps model classes to PPE items via `app/ai/class_map.json`;
  supports optional `no_*` classes; reports which classes the loaded model actually has.
* `app/ai/registry.py` — chooses the detector from `.env`; swap models without code changes.
* `app/services/compliance.py` — thresholds and PASS/FAIL logic, separate from the model.
* *System Settings › Detection & evidence* shows the live status of each class.

## 1. Collect images

* 1,500–3,000 images to start, from the real cameras at the real entry points, in real lighting, all shifts.
* Both compliant and non-compliant examples for **every** item (aim for 300+ examples of each class,
  including each `no_*` class). Stage non-compliant examples safely with volunteers.
* Variety: people, heights, beards, glasses, head coverings, uniform colours, wet/dirty shoes, partial occlusion.
* Obtain consent / follow HR and data-protection rules; store images securely.

## 2. Label

Use a labelling tool (CVAT, Label Studio, Roboflow) and export in **YOLO format**. Classes are listed in
`backend/ai_training/dataset.example.yaml`. Draw a box around each item (and around the place where a
missing item should be, labelled `no_…`). Split by **person/day**, not randomly: 70 % train, 20 % val, 10 % test.

## 3. Train

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -r requirements-ai.txt
Copy-Item ai_training\dataset.example.yaml ai_training\dataset.yaml     # edit `path`
python ai_training\train.py --data ai_training\dataset.yaml --epochs 100 --model yolo11s.pt --device 0
```

A GPU is strongly recommended (`--device 0`); on CPU use fewer epochs for a first trial.

## 4. Validate

```powershell
python ai_training\validate.py --weights runs\ppe\ppe-v1\weights\best.pt --data ai_training\dataset.yaml
```

Review per-class precision and recall on the **test** split. Agree acceptance targets with the food-safety
team (a missed violation is a food-safety risk; a false alarm delays a shift). Then run a **supervised pilot**:
the system advises, a person still decides, and disagreements are reviewed and added to the dataset.

## 5. Load the model

Copy `best.pt` to `backend\models\ppe.pt`, set `AI_MODE=yolo`, check `class_map.json` matches your class
names, restart. Tune *Detection confidence threshold* in System Settings (and per item via the API).

## Model upgrades

Keep each model file with a version name (`ppe-v2.pt`); the version is stored with every detection record,
so results can be traced to the model that produced them.

## Not in scope yet

Employee identification by face is **not** implemented: the entry check takes an employee ID typed or
scanned at the gate (or records an "unidentified person"). Badge/RFID reader integration is a natural next step.
