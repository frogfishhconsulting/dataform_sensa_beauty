from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Generator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.ad_assets import AdAssets
from app.models.cluster import Cluster
from app.models.document import Document
from app.models.enums import Platform, RunStatus
from app.models.run import Run
from app.schemas.ad_assets import AdAssetsOut
from app.schemas.cluster import ClusterOut
from app.schemas.push import GoogleAdsPushRequest, GoogleAdsPushResult
from app.schemas.run import RunCreate, RunSummaryOut
from app.services.google_ads.push import dry_run_validate, push_live
from app.services.pipeline.run_pipeline import run_pipeline
from app.worker.tasks import run_pipeline_task

router = APIRouter()


@router.post("", response_model=dict[str, Any])
def create_run(payload: RunCreate, background: BackgroundTasks, db: Session = Depends(get_db)):
    run = Run(
        topic=payload.topic.strip(),
        recency_days=payload.recency_days,
        status=RunStatus.queued,
        config_json={"topic": payload.topic.strip(), "recency_days": payload.recency_days},
        error_json={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Prefer Celery, but fall back to inline if broker isn't reachable.
    try:
        run_pipeline_task.delay(str(run.id))
    except Exception as e:  # noqa: BLE001
        run.error_json = {**(run.error_json or {}), "celery_dispatch_error": str(e)}
        db.add(run)
        db.commit()
        background.add_task(run_pipeline, str(run.id))

    return {"run_id": str(run.id)}


@router.get("/{run_id}", response_model=RunSummaryOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    counts = dict(
        db.execute(
            select(Document.platform, func.count(Document.id))
            .where(Document.run_id == run_id)
            .group_by(Document.platform)
        ).all()
    )
    document_counts = {p.value: int(counts.get(p, 0)) for p in Platform}
    return {"run": run, "document_counts": document_counts}


@router.get("/{run_id}/results", response_model=dict[str, Any])
def get_results(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    clusters = db.execute(select(Cluster).where(Cluster.run_id == run_id)).scalars().all()
    ad_assets = db.execute(select(AdAssets).where(AdAssets.run_id == run_id).order_by(AdAssets.created_at.desc())).scalars().first()

    return {
        "run": {"id": str(run.id), "status": run.status, "topic": run.topic, "recency_days": run.recency_days},
        "clusters": [ClusterOut.model_validate(c).model_dump() for c in clusters],
        "ad_assets": AdAssetsOut.model_validate(ad_assets).model_dump() if ad_assets else None,
    }


@router.get("/{run_id}/documents", response_model=dict[str, Any])
def get_documents_debug(run_id: uuid.UUID, limit: int = 50, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    docs = (
        db.execute(select(Document).where(Document.run_id == run_id).order_by(Document.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return {
        "run_id": str(run_id),
        "documents": [
            {
                "id": str(d.id),
                "platform": d.platform.value,
                "url": d.url,
                "created_at": d.created_at,
                "title": d.title,
                "text_preview": (d.text or "")[:400],
                "engagement": d.engagement_json,
            }
            for d in docs
        ],
    }


@router.get("/{run_id}/stream")
def stream_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    def gen() -> Generator[bytes, None, None]:
        last_status: str | None = None
        while True:
            run = db.get(Run, run_id)
            if not run:
                yield b"event: error\ndata: {\"detail\":\"run not found\"}\n\n"
                return

            status = run.status.value
            if status != last_status:
                payload = {"run_id": str(run_id), "status": status, "ts": datetime.now(timezone.utc).isoformat()}
                yield f"event: status\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
                last_status = status

            if run.status in (RunStatus.complete, RunStatus.failed, RunStatus.awaiting_approval):
                return
            time.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/{run_id}/dry-run", response_model=GoogleAdsPushResult)
def dry_run(run_id: uuid.UUID, payload: GoogleAdsPushRequest, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    res = dry_run_validate(run_id=str(run_id), req=payload.model_dump())
    return GoogleAdsPushResult(**res)


@router.post("/{run_id}/push", response_model=GoogleAdsPushResult)
def push(run_id: uuid.UUID, payload: GoogleAdsPushRequest, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    if run.status != RunStatus.awaiting_approval:
        raise HTTPException(status_code=400, detail="run is not ready for approval/push")

    res = push_live(run_id=str(run_id), req=payload.model_dump())
    return GoogleAdsPushResult(**res)

