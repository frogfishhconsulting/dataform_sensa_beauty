from __future__ import annotations

from app.services.analysis.clustering import build_clusters


def test_empty_docs_does_not_crash() -> None:
    clustered = build_clusters([])
    assert clustered == {"pain_point": [], "highlight": []}

