from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from app.core.config import settings

log = logging.getLogger("llm")


def _client() -> OpenAI | None:
    if not settings.llm_api_key:
        return None
    return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)


def embed_texts(texts: list[str]) -> list[list[float]] | None:
    client = _client()
    if not client:
        return None
    try:
        res = client.embeddings.create(model=settings.llm_embeddings_model, input=texts)
        return [d.embedding for d in res.data]
    except Exception as e:  # noqa: BLE001
        log.warning("embeddings failed: %s", e)
        return None


def chat_json(system: str, user: str, *, temperature: float = 0.2) -> dict[str, Any] | None:
    client = _client()
    if not client:
        return None
    try:
        res = client.chat.completions.create(
            model=settings.llm_model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = res.choices[0].message.content or ""
        import json

        return json.loads(content)
    except Exception as e:  # noqa: BLE001
        log.warning("chat_json failed: %s", e)
        return None

