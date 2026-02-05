from __future__ import annotations

from langdetect import DetectorFactory, detect

DetectorFactory.seed = 42


def is_english(text: str) -> bool:
    try:
        return detect(text) == "en"
    except Exception:  # noqa: BLE001
        return True  # be permissive if detection fails

