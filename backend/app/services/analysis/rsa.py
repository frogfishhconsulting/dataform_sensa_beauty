from __future__ import annotations

import re
from typing import Any

from app.core.config import settings
from app.services.llm.client import chat_json


HEADLINE_MAX = 30
DESC_MAX = 90


def _trim_to(s: str, max_len: int) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    if len(s) <= max_len:
        return s
    # Trim at word boundary when possible
    cut = s[: max_len + 1].rsplit(" ", 1)[0].strip()
    if cut and len(cut) <= max_len:
        return cut
    return s[:max_len].strip()


def enforce_limits(headlines: list[str], descriptions: list[str]) -> tuple[list[str], list[str], dict[str, Any]]:
    issues: dict[str, Any] = {"headline_too_long": [], "description_too_long": []}
    h2: list[str] = []
    for h in headlines:
        hh = _trim_to(h, HEADLINE_MAX)
        if len(hh) > HEADLINE_MAX:
            issues["headline_too_long"].append({"text": h, "len": len(h)})
        if hh:
            h2.append(hh)
    d2: list[str] = []
    for d in descriptions:
        dd = _trim_to(d, DESC_MAX)
        if len(dd) > DESC_MAX:
            issues["description_too_long"].append({"text": d, "len": len(d)})
        if dd:
            d2.append(dd)
    return h2, d2, issues


SYSTEM_RSA = """You are a Google Ads copywriter creating Responsive Search Ads (RSA).
Return JSON with rsa_sets: array of 2-3 themed sets.
Each set must include:
- theme: short name
- headlines: 25-35 items, each <= 30 chars
- descriptions: 8-12 items, each <= 90 chars
- pin_suggestions: optional pins (e.g. {"H1":"..."}), keep minimal
- notes: brief mapping to pain points/highlights
Avoid prohibited claims (guarantee, cure, instant results), avoid competitor trademarks, and keep headlines distinct."""


def generate_rsa_sets(topic: str, pain_points: list[dict[str, Any]], highlights: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risky_terms = [t.strip() for t in settings.qa_risky_terms_csv.split(",") if t.strip()]
    trademarks = [t.strip() for t in settings.qa_trademarks_csv.split(",") if t.strip()]
    user = {
        "topic": topic,
        "pain_points": [{"label": c["label"], "summary": c["summary"]} for c in pain_points[:10]],
        "highlights": [{"label": c["label"], "summary": c["summary"]} for c in highlights[:6]],
        "constraints": {
            "headline_max_chars": 30,
            "description_max_chars": 90,
            "avoid_terms": risky_terms,
            "avoid_trademarks": trademarks,
        },
    }
    res = chat_json(SYSTEM_RSA, str(user), temperature=0.5)
    if not res or "rsa_sets" not in res:
        # Fallback: template generation
        base = topic.strip()
        headlines = [
            f"Explore {base}"[:HEADLINE_MAX],
            f"{base} Made Simple"[:HEADLINE_MAX],
            f"Compare Options Fast"[:HEADLINE_MAX],
            f"Clear Pricing"[:HEADLINE_MAX],
            f"See Real Reviews"[:HEADLINE_MAX],
            f"Get Started Today"[:HEADLINE_MAX],
        ]
        while len(headlines) < 25:
            headlines.append(_trim_to(f"{base} Insights {len(headlines)+1}", HEADLINE_MAX))
        descriptions = [
            _trim_to(f"See what people say about {base}. Find the right fit with clear info.", DESC_MAX),
            _trim_to("Compare features, pricing, and tradeoffs. No hype—just clarity.", DESC_MAX),
            _trim_to("Build trust with transparent messaging and proof points.", DESC_MAX),
        ]
        while len(descriptions) < 8:
            descriptions.append(_trim_to(f"Learn more about {base} and decide confidently.", DESC_MAX))
        h2, d2, _issues = enforce_limits(headlines, descriptions)
        return [
            {
                "theme": "Core",
                "headlines": h2[:35],
                "descriptions": d2[:12],
                "pin_suggestions": {},
                "notes": "Fallback templates (LLM unavailable).",
            }
        ]

    sets: list[dict[str, Any]] = []
    for s in res.get("rsa_sets") or []:
        h = (s.get("headlines") or [])[:40]
        d = (s.get("descriptions") or [])[:20]
        h2, d2, _issues = enforce_limits(h, d)
        sets.append(
            {
                "theme": (s.get("theme") or "Set").strip()[:40],
                "headlines": h2[:35],
                "descriptions": d2[:12],
                "pin_suggestions": s.get("pin_suggestions") or {},
                "notes": s.get("notes"),
            }
        )
    return sets[:3]

