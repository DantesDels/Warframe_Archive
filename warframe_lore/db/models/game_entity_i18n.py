"""Entité du jeu localisée (issue du Warframe Public Export)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GameEntityI18n(Base):
    """Entité du jeu localisée, issue du Warframe Public Export.

    Une ligne par couple (entité, langue) ; se nourrit des fichiers JSON des
    manifests officiels (``index_<lang>.txt.lzma``).
    """

    __tablename__ = "game_entities_i18n"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True,
                                    autoincrement=True)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lang: Mapped[str] = mapped_column(Text, nullable=False, default="en",
                                      server_default="en")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("entity_id", "lang", name="uq_entities_id_lang"),
        Index("idx_entities_lang", "lang"),
        Index("idx_entities_type", "entity_type"),
    )