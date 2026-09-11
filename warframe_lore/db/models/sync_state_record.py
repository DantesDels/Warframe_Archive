"""Delta mode state (replaces the local ``sync_state.json``)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class SyncStateRecord(Base):
    """Delta mode state (replaces the local ``sync_state.json``).

    Compares the API ``touched`` against the last ``touched`` stored here
    to decide whether a page must be re-downloaded.
    """

    __tablename__ = "sync_state"

    bucket_id: Mapped[str] = mapped_column(Text, primary_key=True)
    page_title: Mapped[str] = mapped_column(Text, primary_key=True)
    page_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    touched: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_sync_bucket", "bucket_id"),
    )