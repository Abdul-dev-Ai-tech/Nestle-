"""Measure a trained model on the held-out test split and print per-class precision/recall.

    python ai_training/validate.py --weights models/ppe.pt --data ai_training/dataset.yaml

Acceptance is a site decision. As a starting point, do not rely on a class at the door until its
recall on the *test* split (images the model never saw, from the real cameras) meets the target
agreed with the factory's food-safety team, and it has passed a supervised pilot.
"""
import argparse

from ultralytics import YOLO


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", default="test")
    ap.add_argument("--imgsz", type=int, default=960)
    args = ap.parse_args()
    model = YOLO(args.weights)
    metrics = model.val(data=args.data, split=args.split, imgsz=args.imgsz, verbose=False)
    print(f"\n{'class':<18}{'precision':>10}{'recall':>10}{'mAP50':>10}")
    for i, name in model.names.items():
        try:
            p, r, ap50, _ = metrics.class_result(list(metrics.ap_class_index).index(i))
            print(f"{name:<18}{p:>10.3f}{r:>10.3f}{ap50:>10.3f}")
        except ValueError:
            print(f"{name:<18}{'no test images for this class':>30}")
    print(f"\nOverall mAP50 = {metrics.box.map50:.3f}, mAP50-95 = {metrics.box.map:.3f}")


if __name__ == "__main__":
    main()
