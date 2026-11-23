"""Inbound port for human curation actions."""

from __future__ import annotations

from typing import Protocol


class CurationPort(Protocol):
    """Inbound: review, approve, suspend, blacklist sources/candidates."""

    def approve(self, universe_id: str, candidate_id: str) -> None: ...
    def blacklist(self, universe_id: str, source_id: str) -> None: ...
