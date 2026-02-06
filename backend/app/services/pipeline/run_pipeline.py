from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.ad_assets import AdAssets
from app.models.cluster import Cluster
from app.models.document import Document
from app.models.enums import ClusterType, RunStatus
from app.models.run import Run
from app.services.analysis.clustering import build_clusters
from app.services.analysis.dedupe import dedupe_texts
from app.services.analysis.language import is_english
from app.services.analysis.qa import qa_rsa_sets
from app.services.analysis.rsa import generate_rsa_sets
from app.services.analysis.summarize import summarize_cluster
from app.services.collectors.base import MissingCredentials
from app.services.collectors.reddit import RedditCollector
from app.services.collectors.x import XCollector
from app.services.collectors.youtube import YouTubeCollector
from app.services.utils.text import clean_text

log = logging.getLogger("pipeline")


def _set_status(db: Session, run: Run, status: RunStatus) -> None:
    run.status = status
    db.add(run)
    db.commit()


def _merge_error(run: Run, patch: dict) -> None:
    current = run.error_json or {}
    run.error_json = {**current, **patch}


def run_pipeline(run_id: str) -> dict:
    db: Session = SessionLocal()
    rid = uuid.UUID(run_id)
    try:
        run = db.get(Run, rid)
        if not run:
            return {"ok": False, "error": "run not found"}

        _set_status(db, run, RunStatus.collecting)
        since = datetime.now(timezone.utc) - timedelta(days=int(run.recency_days))

        collector_errors: dict = {}
        collected_counts: dict[str, int] = {"reddit": 0, "x": 0, "youtube": 0}

        collectors = []
        for ctor in (RedditCollector, XCollector, YouTubeCollector):
            try:
                collectors.append(ctor())
            except MissingCredentials as e:
                name = getattr(ctor, "__name__", "collector")
                platform = "reddit" if "Reddit" in name else ("youtube" if "YouTube" in name else "x")
                collector_errors[platform] = {"skipped": True, "reason": str(e)}

        collected_by_platform: dict[str, list] = {}
        if collectors:
            with ThreadPoolExecutor(max_workers=min(3, len(collectors))) as ex:
                futures = {ex.submit(c.collect, run.topic, since): c for c in collectors}
                for fut in as_completed(futures):
                    c = futures[fut]
                    try:
                        docs = fut.result()
                        collected_by_platform[c.platform] = docs
                        collected_counts[c.platform] = len(docs)
                    except Exception as e:  # noqa: BLE001
                        log.exception("collector failed", extra={"run_id": run_id, "step": "collect", "topic": run.topic})
                        collector_errors[c.platform] = {"error": str(e)}

        # Store documents after collection so DB session is single-threaded.
        for platform, docs in collected_by_platform.items():
            for nd in docs:
                d = Document(
                    run_id=rid,
                    platform=nd.platform,
                    source_id=nd.source_id,
                    url=nd.url,
                    author=nd.author,
                    created_at=nd.created_at,
                    engagement_json=nd.engagement,
                    title=nd.title,
                    text=clean_text(nd.text),
                    raw_json=nd.raw,
                )
                db.add(d)
            db.commit()

        _merge_error(run, {"collectors": collector_errors, "collected_counts": collected_counts})
        db.add(run)
        db.commit()

        _set_status(db, run, RunStatus.analyzing)

        docs = db.execute(select(Document).where(Document.run_id == rid)).scalars().all()
        texts = [d.text or "" for d in docs]
        # preprocess: language + dedupe
        english_idxs = [i for i, t in enumerate(texts) if t and is_english(t)]
        texts_en = [texts[i] for i in english_idxs]
        keep_local = dedupe_texts(texts_en, threshold=95)
        kept_doc_idxs = [english_idxs[i] for i in keep_local]

        docs_kept = [docs[i] for i in kept_doc_idxs]
        doc_rows = [{"id": d.id, "url": d.url, "text": d.text, "engagement_json": d.engagement_json} for d in docs_kept]

        # Replace prior clusters/ad assets for re-runs
        db.execute(delete(Cluster).where(Cluster.run_id == rid))
        db.execute(delete(AdAssets).where(AdAssets.run_id == rid))
        db.commit()

        clustered = build_clusters(doc_rows, top_pain=10, top_highlight=6)
        clusters_out: list[Cluster] = []
        for ctype, items in clustered.items():
            for c in items:
                label, summary = summarize_cluster(run.topic, c.get("summary_seed_texts") or [], c.get("label") or "Cluster")
                clusters_out.append(
                    Cluster(
                        run_id=rid,
                        type=ClusterType.pain_point if ctype == "pain_point" else ClusterType.highlight,
                        label=label,
                        summary=summary,
                        intensity_score=float(c.get("intensity_score") or 0.0),
                        evidence=c.get("evidence") or [],
                    )
                )
        for row in clusters_out:
            db.add(row)
        db.commit()

        _set_status(db, run, RunStatus.drafting)
        pain = [c for c in clusters_out if c.type == ClusterType.pain_point]
        high = [c for c in clusters_out if c.type == ClusterType.highlight]
        rsa_sets = generate_rsa_sets(
            run.topic,
            pain_points=[{"label": c.label, "summary": c.summary} for c in pain],
            highlights=[{"label": c.label, "summary": c.summary} for c in high],
        )
        rsa_sets_clean, qa_report = qa_rsa_sets(rsa_sets)

        aa = AdAssets(run_id=rid, rsa_sets=rsa_sets_clean, qa_report=qa_report, final_selection=None)
        db.add(aa)
        db.commit()

        _set_status(db, run, RunStatus.awaiting_approval)
        return {"ok": True, "run_id": run_id}
    except Exception as e:  # noqa: BLE001
        log.exception("pipeline failed", extra={"run_id": run_id, "step": "pipeline"})
        try:
            run = db.get(Run, rid)
            if run:
                run.status = RunStatus.failed
                _merge_error(run, {"pipeline_error": str(e)})
                db.add(run)
                db.commit()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": False, "error": str(e)}
    finally:
        db.close()

