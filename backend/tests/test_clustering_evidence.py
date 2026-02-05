from __future__ import annotations

import uuid

from app.services.analysis.clustering import build_clusters


def test_clustering_produces_evidence_links() -> None:
    docs = [
        {"id": uuid.uuid4(), "url": "https://example.com/a", "text": "I can't get this to work. It's broken.", "engagement_json": {"likes": 10}},
        {"id": uuid.uuid4(), "url": "https://example.com/b", "text": "Setup was difficult and slow.", "engagement_json": {"likes": 2}},
        {"id": uuid.uuid4(), "url": "https://example.com/c", "text": "Love how fast this is. Works great.", "engagement_json": {"likes": 5}},
        {"id": uuid.uuid4(), "url": "https://example.com/d", "text": "Amazing results, easy to use.", "engagement_json": {"likes": 1}},
    ]

    clustered = build_clusters(docs, top_pain=10, top_highlight=6)
    assert "pain_point" in clustered and "highlight" in clustered

    any_evidence = False
    for group in (clustered["pain_point"] + clustered["highlight"]):
        for ev in group.get("evidence") or []:
            any_evidence = True
            assert ev["url"].startswith("http")
            assert isinstance(ev["quote"], str) and len(ev["quote"]) > 0
            assert isinstance(ev["document_id"], str) and len(ev["document_id"]) > 0
    assert any_evidence

