from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from youtube_transcript_api import YouTubeTranscriptApi

from app.core.config import settings
from app.models.enums import Platform
from app.services.collectors.base import Collector, MissingCredentials
from app.services.types import NormalizedDocument
from app.services.utils.text import clean_text

log = logging.getLogger("collector.youtube")


def _chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end].strip())
        start = end
    return [c for c in chunks if c]


class YouTubeCollector(Collector):
    platform = "youtube"

    def __init__(self) -> None:
        if not settings.youtube_api_key:
            raise MissingCredentials("missing youtube_api_key")

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=20))
    def _get(self, client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
        r = client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    def collect(self, topic: str, since_datetime: datetime) -> list[NormalizedDocument]:
        out: list[NormalizedDocument] = []
        with httpx.Client(timeout=30) as client:
            params = {
                "part": "snippet",
                "q": topic,
                "type": "video",
                "maxResults": 10,
                "publishedAfter": since_datetime.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "key": settings.youtube_api_key,
            }
            data = self._get(client, "https://www.googleapis.com/youtube/v3/search", params=params)
            for item in data.get("items", []) or []:
                video_id = ((item.get("id") or {}).get("videoId")) or ""
                if not video_id:
                    continue
                snip = item.get("snippet") or {}
                published_at = snip.get("publishedAt")
                created = (
                    datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                    if published_at
                    else datetime.now(timezone.utc)
                )
                title = clean_text(snip.get("title") or "")
                channel = snip.get("channelTitle")
                url = f"https://www.youtube.com/watch?v={video_id}"

                transcript_text = ""
                try:
                    lines = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
                    transcript_text = clean_text(" ".join([l.get("text", "") for l in lines]))
                except Exception as e:  # noqa: BLE001
                    log.info("transcript unavailable for %s: %s", video_id, e)

                base_text = clean_text("\n\n".join([title, transcript_text]).strip())
                for idx, chunk in enumerate(_chunk_text(base_text, max_chars=4500), start=1):
                    out.append(
                        NormalizedDocument(
                            platform=Platform.youtube,
                            source_id=f"{video_id}#{idx}",
                            url=url,
                            author=channel,
                            created_at=created,
                            title=title or None,
                            text=chunk,
                            engagement={},  # views/likes require extra API calls; optional
                            raw={"search_item": item, "has_transcript": bool(transcript_text)},
                        )
                    )
        return out

