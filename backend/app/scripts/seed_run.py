from __future__ import annotations

import argparse
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import RunStatus
from app.models.run import Run
from app.services.pipeline.run_pipeline import run_pipeline


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--topic", required=True)
    p.add_argument("--recency-days", type=int, default=14)
    args = p.parse_args()

    db: Session = SessionLocal()
    try:
        run = Run(topic=args.topic.strip(), recency_days=args.recency_days, status=RunStatus.queued, config_json={}, error_json={})
        db.add(run)
        db.commit()
        db.refresh(run)
        print(f"Created run_id={run.id}")
    finally:
        db.close()

    res = run_pipeline(str(run.id))
    print(res)


if __name__ == "__main__":
    main()

