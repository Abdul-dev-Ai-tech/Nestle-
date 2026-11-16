"""Delete evidence images older than the retention period. Schedule daily (Task Scheduler / cron).

    python -m scripts.purge_evidence            # uses EVIDENCE_RETENTION_DAYS
    python -m scripts.purge_evidence --days 180
"""
import argparse

from app.core.config import get_settings
from app.services.storage import purge_evidence_older_than

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=get_settings().EVIDENCE_RETENTION_DAYS)
    args = ap.parse_args()
    print(f"Removed {purge_evidence_older_than(args.days)} evidence file(s) older than {args.days} days.")
