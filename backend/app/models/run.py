from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RunStatus


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    recency_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus, name="run_status"), nullable=False, default=RunStatus.queued)

    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    documents = relationship("Document", back_populates="run", cascade="all, delete-orphan")
    clusters = relationship("Cluster", back_populates="run", cascade="all, delete-orphan")
    ad_assets = relationship("AdAssets", back_populates="run", cascade="all, delete-orphan")
    pushes = relationship("GoogleAdsPush", back_populates="run", cascade="all, delete-orphan")

