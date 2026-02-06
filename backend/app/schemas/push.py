from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GoogleAdsPushRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    ad_group_id: str = Field(min_length=1)
    final_url: str = Field(min_length=5)
    assets: dict[str, Any]


class GoogleAdsPushResult(BaseModel):
    ok: bool
    status: str
    message: str | None = None
    request_payload: dict[str, Any] = {}
    response_payload: dict[str, Any] = {}

