from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from app.core.config import settings
from app.services.analysis.rsa import DESC_MAX, HEADLINE_MAX, enforce_limits
from app.services.llm.client import chat_json
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


def _trim_len(s: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= max_len:
        return s
    cut = s[: max_len + 1].rsplit(" ", 1)[0].strip()
    if cut and len(cut) <= max_len:
        return cut
    return s[:max_len].strip()


def _rewrite_heuristic(text: str, max_len: int) -> str:
    risky = [t.strip().lower() for t in settings.qa_risky_terms_csv.split(",") if t.strip()]
    trademarks = [t.strip().lower() for t in settings.qa_trademarks_csv.split(",") if t.strip()]

    out = re.sub(r"\s+", " ", (text or "").strip())
    low = out.lower()
    for t in risky:
        if t and t in low:
            out = re.sub(re.escape(t), "", out, flags=re.IGNORECASE).strip()
            low = out.lower()
    for tm in trademarks:
        if tm and tm in low:
            out = re.sub(re.escape(tm), "", out, flags=re.IGNORECASE).strip()
            low = out.lower()
    out = re.sub(r"\s+", " ", out).strip()
    return _trim_len(out, max_len)


def _rewrite_with_llm(text: str, max_len: int) -> str | None:
    system = "You rewrite ad copy safely and tersely."
    user = {
        "text": text,
        "max_chars": max_len,
        "avoid_terms": [t.strip() for t in settings.qa_risky_terms_csv.split(",") if t.strip()],
        "avoid_trademarks": [t.strip() for t in settings.qa_trademarks_csv.split(",") if t.strip()],
        "instructions": "Return JSON: {\"rewrite\": \"...\"}. Must be <= max_chars.",
    }
    res = chat_json(system, str(user), temperature=0.3)
    if not res:
        return None
    rw = (res.get("rewrite") or "").strip()
    if rw and len(rw) <= max_len:
        return rw
    return None


def _rewrite(text: str, max_len: int) -> str:
    return _rewrite_with_llm(text, max_len) or _rewrite_heuristic(text, max_len)


def qa_rsa_sets(rsa_sets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report: dict[str, Any] = {"sets": [], "overall": {}}
    cleaned_sets: list[dict[str, Any]] = []

    for s in rsa_sets:
        headlines = list(s.get("headlines") or [])
        descriptions = list(s.get("descriptions") or [])

        headlines, descriptions, limit_issues = enforce_limits(headlines, descriptions)
        headlines, dup_h = _uniq_keep(headlines)
        descriptions, dup_d = _uniq_keep(descriptions)
        policy_h = _policy_flags(headlines)
        policy_d = _policy_flags(descriptions)

        rewrites = {"headlines": [], "descriptions": []}
        for item in (limit_issues.get("headline_too_long") or []):
            t = item.get("text") or ""
            rewrites["headlines"].append({"original": t, "rewrite": _rewrite(t, HEADLINE_MAX), "reason": "over_limit"})
        for item in (limit_issues.get("description_too_long") or []):
            t = item.get("text") or ""
            rewrites["descriptions"].append({"original": t, "rewrite": _rewrite(t, DESC_MAX), "reason": "over_limit"})

        for f in policy_h:
            t = f.get("text") or ""
            rewrites["headlines"].append({"original": t, "rewrite": _rewrite(t, HEADLINE_MAX), "reason": "policy_terms", **f})
        for f in policy_d:
            t = f.get("text") or ""
            rewrites["descriptions"].append({"original": t, "rewrite": _rewrite(t, DESC_MAX), "reason": "policy_terms", **f})

        # Duplicates: suggest an alternative variant or removal.
        for d in dup_h:
            t = d.get("text") or ""
            rewrites["headlines"].append(
                {
                    "original": t,
                    "rewrite": _rewrite(f"Compare {t}", HEADLINE_MAX) if t else "",
                    "reason": "duplicate",
                    **d,
                }
            )
        for d in dup_d:
            t = d.get("text") or ""
            rewrites["descriptions"].append(
                {
                    "original": t,
                    "rewrite": _rewrite(f"Learn why: {t}", DESC_MAX) if t else "",
                    "reason": "duplicate",
                    **d,
                }
            )

        policy = {"headlines": policy_h, "descriptions": policy_d}

        set_report = {
            "theme": s.get("theme"),
            "limit_issues": limit_issues,
            "duplicates": {"headlines": dup_h, "descriptions": dup_d},
            "policy_flags": policy,
            "rewrites": rewrites,
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

    report["overall"]["has_policy_flags"] = any(
        len(s["policy_flags"]["headlines"]) or len(s["policy_flags"]["descriptions"]) for s in report["sets"]
    )
    report["overall"]["has_duplicate_flags"] = any(
        len(s["duplicates"]["headlines"]) or len(s["duplicates"]["descriptions"]) for s in report["sets"]
    )
    return cleaned_sets, report

