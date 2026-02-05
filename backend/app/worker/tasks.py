from __future__ import annotations

import logging

from app.services.pipeline.run_pipeline import run_pipeline
from app.worker.celery_app import celery_app

log = logging.getLogger("worker")


@celery_app.task(name="run_pipeline_task")
def run_pipeline_task(run_id: str) -> dict:
    return run_pipeline(run_id)

