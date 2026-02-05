from __future__ import annotations

from app.services.analysis.dedupe import dedupe_texts


def test_dedupe_removes_near_duplicates() -> None:
    texts = [
        "This product is great! https://example.com",
        "This product is great!",
        "Completely different sentence.",
    ]
    keep = dedupe_texts(texts, threshold=90)
    kept_texts = [texts[i] for i in keep]
    assert len(kept_texts) == 2
    assert "Completely different sentence." in kept_texts

