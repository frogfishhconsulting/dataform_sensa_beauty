from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import RunStatus


class RunCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    recency_days: int = Field(ge=1, le=365)


class RunOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    user_id: str | None
    topic: str
    recency_days: int
    status: RunStatus
    config_json: dict[str, Any]
    error_json: dict[str, Any]

    class Config:
        from_attributes = True


class RunSummaryOut(BaseModel):
    run: RunOut
    document_counts: dict[str, int]

