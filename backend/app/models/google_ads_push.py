from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PushStatus


class GoogleAdsPush(Base):
    __tablename__ = "google_ads_pushes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), index=True)

    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    campaign_id: Mapped[str] = mapped_column(String, nullable=False)
    ad_group_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[PushStatus] = mapped_column(Enum(PushStatus, name="push_status"), nullable=False)

    request_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    response_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    run = relationship("Run", back_populates="pushes")

