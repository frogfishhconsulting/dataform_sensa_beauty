from __future__ import annotations

from app.services.llm.client import chat_json


SYSTEM = """You are an expert marketing analyst.
Given a cluster of social posts, output JSON with:
- label: short crisp label (<= 60 chars)
- summary: 3-5 sentences, include:
  - what the cluster is about
  - who is saying this (persona guess)
  - implications: 2-3 ad angles
Avoid strong medical/legal claims, guarantees, and do not mention competitors/trademarks unless present in the text."""


def summarize_cluster(topic: str, seed_texts: list[str], fallback_label: str) -> tuple[str, str]:
    user = {
        "topic": topic,
        "examples": seed_texts[:10],
        "output_constraints": {"label_max_chars": 60},
    }
    res = chat_json(SYSTEM, str(user))
    if not res:
        # Simple fallback
        summary = (
            f"{fallback_label}: Common theme in recent discussion about {topic}. "
            f"Persona: people actively researching or comparing options. "
            f"Implications: emphasize clarity, time-savings, and reduced risk."
        )
        return fallback_label[:60], summary

    label = (res.get("label") or fallback_label).strip()[:60]
    summary = (res.get("summary") or "").strip() or (
        f"{label}: Common theme in recent discussion about {topic}. Persona: evaluators. Implications: trust, speed, clarity."
    )
    return label, summary

