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

log = logging.getLogger("collector.reddit")


class RedditCollector(Collector):
    platform = "reddit"

    def __init__(self) -> None:
        if not settings.reddit_client_id:
            raise MissingCredentials("missing reddit_client_id")

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(min=1, max=20))
    def _get_token(self) -> str:
        # Prefer "password" grant for script apps (most reliable for /search + comments).
        # Fallback to client_credentials for app-only access.
        auth = (settings.reddit_client_id, settings.reddit_client_secret or "")
        if settings.reddit_username and settings.reddit_password:
            data = {
                "grant_type": "password",
                "username": settings.reddit_username,
                "password": settings.reddit_password,
                "scope": "read",
            }
        else:
            data = {"grant_type": "client_credentials", "scope": "read"}
        headers = {"User-Agent": settings.reddit_user_agent}
        r = httpx.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers, timeout=20)
        r.raise_for_status()
        return r.json()["access_token"]

    def collect(self, topic: str, since_datetime: datetime) -> list[NormalizedDocument]:
        token = self._get_token()
        headers = {"Authorization": f"bearer {token}", "User-Agent": settings.reddit_user_agent}

        # Reddit search is not strictly bounded by time; we filter client-side.
        params = {
            "q": topic,
            "sort": "top",
            "t": "month",  # closest supported; we'll filter using created_utc
            "limit": 25,
            "include_over_18": "on",
            "type": "link",
        }
        out: list[NormalizedDocument] = []
        with httpx.Client(headers=headers, timeout=30) as client:
            resp = client.get("https://oauth.reddit.com/search", params=params)
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])

            for child in posts:
                d = child.get("data", {})
                created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
                if created < since_datetime:
                    continue

                permalink = d.get("permalink") or ""
                url = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else (d.get("url") or "")
                post_id = d.get("id") or ""
                title = clean_text(d.get("title") or "")
                selftext = clean_text(d.get("selftext") or "")

                # Pull some top comments for additional signals.
                comments_text = ""
                try:
                    c = client.get(f"https://oauth.reddit.com/comments/{post_id}", params={"limit": 10, "sort": "top"})
                    if c.status_code == 200:
                        comments = c.json()[1].get("data", {}).get("children", [])
                        top_comments: list[str] = []
                        for cc in comments[:8]:
                            cd = cc.get("data", {})
                            body = clean_text(cd.get("body") or "")
                            if body:
                                top_comments.append(body)
                        if top_comments:
                            comments_text = "\n\nTop comments:\n" + "\n- ".join([""] + top_comments[:6])
                except Exception as e:  # noqa: BLE001
                    log.warning("comment fetch failed: %s", e)

                text = clean_text("\n\n".join([title, selftext, comments_text]).strip())
                if not text:
                    continue

                engagement: dict[str, Any] = {
                    "upvotes": d.get("ups"),
                    "comments": d.get("num_comments"),
                    "score": d.get("score"),
                }
                raw: dict[str, Any] = {"post": d}

                out.append(
                    NormalizedDocument(
                        platform=Platform.reddit,
                        source_id=str(post_id),
                        url=url or f"https://www.reddit.com{permalink}",
                        author=d.get("author"),
                        created_at=created,
                        title=title or None,
                        text=text,
                        engagement=engagement,
                        raw=raw,
                    )
                )
        return out

