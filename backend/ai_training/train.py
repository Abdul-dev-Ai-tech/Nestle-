"""Train a YOLO PPE detector on your own labelled images.

    pip install -r requirements-ai.txt
    python ai_training/train.py --data ai_training/dataset.yaml --epochs 100 --model yolo11s.pt

The best weights are written to runs/ppe/<name>/weights/best.pt. Copy them to backend/models/ppe.pt
and set AI_MODE=yolo. Validate with ai_training/validate.py BEFORE using the model at a door.
"""
import argparse

from ultralytics import YOLO


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dataset.yaml")
    ap.add_argument("--model", default="yolo11s.pt", help="pretrained starting weights (transfer learning)")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=960, help="larger helps small items such as beard nets")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default="cpu", help="'cpu', '0' for the first GPU")
    ap.add_argument("--name", default="ppe-v1")
    args = ap.parse_args()
    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=args.device,
                project="runs/ppe", name=args.name, patience=20, seed=0)
    print("Training finished. Validate the model before use: python ai_training/validate.py --weights <best.pt> --data", args.data)


if __name__ == "__main__":
    main()
