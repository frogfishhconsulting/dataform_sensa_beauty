from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import Platform


@dataclass(frozen=True)
class NormalizedDocument:
    platform: Platform
    source_id: str
    url: str
    created_at: datetime
    text: str
    title: str | None = None
    author: str | None = None
    engagement: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

