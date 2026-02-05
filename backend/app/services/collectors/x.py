from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.enums import Platform
from app.services.collectors.base import Collector, MissingCredentials
from app.services.types import NormalizedDocument
from app.services.utils.text import clean_text

log = logging.getLogger("collector.x")


class XCollector(Collector):
    platform = "x"

    def __init__(self) -> None:
        if not settings.x_bearer_token:
            raise MissingCredentials("missing x_bearer_token")

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=20))
    def _get(self, client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
        r = client.get(url, params=params)
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(r.text, request=r.request, response=r)
        return r.json()

    def collect(self, topic: str, since_datetime: datetime) -> list[NormalizedDocument]:
        headers = {"Authorization": f"Bearer {settings.x_bearer_token}"}
        query = f'({topic}) -is:retweet lang:en'
        params = {
            "query": query,
            "max_results": 50,
            "start_time": since_datetime.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tweet.fields": "created_at,public_metrics,author_id,lang",
        }
        out: list[NormalizedDocument] = []
        with httpx.Client(headers=headers, timeout=30) as client:
            data = self._get(client, "https://api.x.com/2/tweets/search/recent", params=params)
            for t in data.get("data", []) or []:
                created_at = t.get("created_at")
                if not created_at:
                    continue
                created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                text = clean_text(t.get("text") or "")
                if not text:
                    continue
                metrics = t.get("public_metrics") or {}
                engagement = {
                    "likes": metrics.get("like_count"),
                    "replies": metrics.get("reply_count"),
                    "retweets": metrics.get("retweet_count"),
                    "quotes": metrics.get("quote_count"),
                }
                tweet_id = str(t.get("id"))
                url = f"https://x.com/i/web/status/{tweet_id}"
                out.append(
                    NormalizedDocument(
                        platform=Platform.x,
                        source_id=tweet_id,
                        url=url,
                        author=str(t.get("author_id")) if t.get("author_id") else None,
                        created_at=created,
                        title=None,
                        text=text,
                        engagement=engagement,
                        raw={"tweet": t},
                    )
                )
        return out

