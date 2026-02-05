from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.enums import ClusterType


class EvidenceItem(BaseModel):
    document_id: uuid.UUID
    quote: str
    url: str
    meta: dict[str, Any] = {}


class ClusterOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    type: ClusterType
    label: str
    summary: str
    intensity_score: float
    evidence: list[EvidenceItem]
    created_at: datetime

    class Config:
        from_attributes = True

