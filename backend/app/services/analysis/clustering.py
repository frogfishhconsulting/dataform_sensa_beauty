from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from app.services.llm.client import embed_texts
from app.services.utils.text import clean_text, snippet


def _engagement_score(eng: dict[str, Any]) -> float:
    score = 0.0
    for k in ("likes", "upvotes", "views", "replies", "comments", "retweets", "quotes", "score"):
        v = eng.get(k)
        try:
            if v is not None:
                score += float(v)
        except Exception:  # noqa: BLE001
            continue
    return math.log1p(max(score, 0.0))


def _fallback_vectors(texts: list[str]) -> np.ndarray:
    vec = TfidfVectorizer(stop_words="english", max_features=2048)
    m = vec.fit_transform(texts)
    return m.toarray()


def cluster_texts(texts: list[str], *, max_k: int = 12) -> tuple[list[int], np.ndarray]:
    cleaned = [clean_text(t) for t in texts]
    emb = embed_texts(cleaned)
    if emb:
        X = np.array(emb, dtype=np.float32)
    else:
        X = _fallback_vectors(cleaned)

    n = len(cleaned)
    if n <= 2:
        return [0] * n, X

    k = min(max(2, int(round(math.sqrt(n)))), max_k, n)
    km = KMeans(n_clusters=k, random_state=42, n_init="auto")
    labels = km.fit_predict(X)
    return labels.tolist(), X


NEG_HINTS = {"problem", "issue", "annoy", "annoying", "hard", "difficult", "can't", "cannot", "expensive", "cost", "slow", "bug", "broken", "fail"}
POS_HINTS = {"love", "great", "awesome", "easy", "fast", "works", "helped", "amazing", "recommend", "solid"}


def classify_cluster(texts: list[str]) -> str:
    joined = " ".join(texts).lower()
    neg = sum(1 for w in NEG_HINTS if w in joined)
    pos = sum(1 for w in POS_HINTS if w in joined)
    return "pain_point" if neg >= pos else "highlight"


def label_cluster(texts: list[str]) -> str:
    vec = TfidfVectorizer(stop_words="english", max_features=64, ngram_range=(1, 2))
    X = vec.fit_transform(texts)
    sums = X.sum(axis=0).A1
    terms = vec.get_feature_names_out()
    pairs = sorted(zip(sums, terms), reverse=True)[:6]
    label = ", ".join([t for _, t in pairs[:3]]).strip()
    return label[:80] if label else "Cluster"


def build_clusters(
    docs: list[dict[str, Any]],
    *,
    top_pain: int = 10,
    top_highlight: int = 6,
) -> dict[str, list[dict[str, Any]]]:
    """
    docs: list of {id, url, text, engagement_json}
    Returns {"pain_point":[...], "highlight":[...]} cluster dicts with evidence.
    """
    texts = [d["text"] for d in docs]
    labels, _X = cluster_texts(texts)
    groups: dict[int, list[int]] = defaultdict(list)
    for i, lab in enumerate(labels):
        groups[lab].append(i)

    cluster_rows: list[dict[str, Any]] = []
    for _, idxs in groups.items():
        c_texts = [texts[i] for i in idxs]
        c_type = classify_cluster(c_texts)
        c_label = label_cluster(c_texts)
        # evidence: prioritize engagement
        scored = sorted(
            idxs,
            key=lambda i: (_engagement_score(docs[i].get("engagement_json") or {}), len(texts[i])),
            reverse=True,
        )
        evidence = []
        for i in scored[:6]:
            evidence.append(
                {
                    "document_id": str(docs[i]["id"]),
                    "quote": snippet(texts[i], 260),
                    "url": docs[i]["url"],
                    "meta": {"engagement_score": _engagement_score(docs[i].get("engagement_json") or {})},
                }
            )
        intensity = float(len(idxs)) + sum(_engagement_score(docs[i].get("engagement_json") or {}) for i in idxs)
        cluster_rows.append(
            {
                "type": c_type,
                "label": c_label,
                "summary_seed_texts": c_texts[:12],
                "intensity_score": intensity,
                "evidence": evidence[:6],
            }
        )

    pains = sorted([c for c in cluster_rows if c["type"] == "pain_point"], key=lambda c: c["intensity_score"], reverse=True)[
        :top_pain
    ]
    highs = sorted([c for c in cluster_rows if c["type"] == "highlight"], key=lambda c: c["intensity_score"], reverse=True)[
        :top_highlight
    ]

    # If classification is lopsided, rebalance by splitting top clusters.
    if len(pains) < 6:
        rest = sorted([c for c in cluster_rows if c not in pains], key=lambda c: c["intensity_score"], reverse=True)
        for c in rest:
            if len(pains) >= 6:
                break
            c2 = dict(c)
            c2["type"] = "pain_point"
            pains.append(c2)
    if len(highs) < 4:
        rest = sorted([c for c in cluster_rows if c not in highs], key=lambda c: c["intensity_score"], reverse=True)
        for c in rest:
            if len(highs) >= 4:
                break
            c2 = dict(c)
            c2["type"] = "highlight"
            highs.append(c2)

    return {"pain_point": pains[:top_pain], "highlight": highs[:top_highlight]}

