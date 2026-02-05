from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from app.core.config import settings
from app.services.analysis.rsa import DESC_MAX, HEADLINE_MAX, enforce_limits
from app.services.utils.text import normalize_for_compare


def _uniq_keep(items: list[str], *, near_dup_threshold: int = 92) -> tuple[list[str], list[dict[str, Any]]]:
    kept: list[str] = []
    issues: list[dict[str, Any]] = []
    norms: list[str] = []
    for s in items:
        s = re.sub(r"\s+", " ", (s or "").strip())
        if not s:
            continue
        ns = normalize_for_compare(s)
        dup_of = None
        for j, prior in enumerate(norms):
            if fuzz.token_set_ratio(ns, prior) >= near_dup_threshold:
                dup_of = kept[j]
                break
        if dup_of:
            issues.append({"text": s, "duplicate_of": dup_of})
            continue
        kept.append(s)
        norms.append(ns)
    return kept, issues


def _policy_flags(items: list[str]) -> list[dict[str, Any]]:
    risky = [t.strip().lower() for t in settings.qa_risky_terms_csv.split(",") if t.strip()]
    trademarks = [t.strip().lower() for t in settings.qa_trademarks_csv.split(",") if t.strip()]
    flags: list[dict[str, Any]] = []
    for s in items:
        low = (s or "").lower()
        hit_terms = [t for t in risky if t in low]
        hit_tm = [t for t in trademarks if t and t in low]
        if hit_terms or hit_tm:
            flags.append({"text": s, "risky_terms": hit_terms, "trademarks": hit_tm})
    return flags


def qa_rsa_sets(rsa_sets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report: dict[str, Any] = {"sets": [], "overall": {}}
    cleaned_sets: list[dict[str, Any]] = []

    for s in rsa_sets:
        headlines = list(s.get("headlines") or [])
        descriptions = list(s.get("descriptions") or [])

        headlines, descriptions, limit_issues = enforce_limits(headlines, descriptions)
        headlines, dup_h = _uniq_keep(headlines)
        descriptions, dup_d = _uniq_keep(descriptions)
        policy = _policy_flags(headlines + descriptions)

        set_report = {
            "theme": s.get("theme"),
            "limit_issues": limit_issues,
            "duplicates": {"headlines": dup_h, "descriptions": dup_d},
            "policy_flags": policy,
            "counts": {
                "headlines": len(headlines),
                "descriptions": len(descriptions),
                "headline_max": HEADLINE_MAX,
                "description_max": DESC_MAX,
            },
        }
        report["sets"].append(set_report)

        cleaned_sets.append(
            {
                **s,
                "headlines": headlines[:35],
                "descriptions": descriptions[:12],
            }
        )

    report["overall"]["has_policy_flags"] = any(len(s["policy_flags"]) for s in report["sets"])
    report["overall"]["has_duplicate_flags"] = any(
        len(s["duplicates"]["headlines"]) or len(s["duplicates"]["descriptions"]) for s in report["sets"]
    )
    return cleaned_sets, report

