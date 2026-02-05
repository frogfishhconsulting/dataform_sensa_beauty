from __future__ import annotations

from rapidfuzz import fuzz

from app.services.utils.text import normalize_for_compare


def dedupe_texts(texts: list[str], threshold: int = 95) -> list[int]:
    """
    Returns indices of texts to KEEP.
    Uses token_sort_ratio on normalized strings; robust enough for small/medium batches.
    """
    keep: list[int] = []
    seen_norms: list[str] = []
    for i, t in enumerate(texts):
        nt = normalize_for_compare(t)
        if not nt:
            continue
        is_dup = False
        for s in seen_norms:
            if fuzz.token_sort_ratio(nt, s) >= threshold:
                is_dup = True
                break
        if not is_dup:
            keep.append(i)
            seen_norms.append(nt)
    return keep

