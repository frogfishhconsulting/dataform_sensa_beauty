from __future__ import annotations

import re


_WS_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+")


def clean_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\u200b", " ")
    text = _WS_RE.sub(" ", text)
    return text.strip()


def snippet(text: str, max_len: int = 240) -> str:
    text = clean_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def normalize_for_compare(text: str) -> str:
    text = (text or "").lower()
    text = _URL_RE.sub("", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text

