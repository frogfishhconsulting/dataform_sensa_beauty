from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RsaDraft(BaseModel):
    theme: str
    headlines: list[str] = Field(default_factory=list)
    descriptions: list[str] = Field(default_factory=list)
    pin_suggestions: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class AdAssetsOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    rsa_sets: list[dict[str, Any]]
    final_selection: dict[str, Any] | None
    qa_report: dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True

