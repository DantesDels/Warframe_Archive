"""Outbound port for the vault exporter used by the synthesizer."""

from __future__ import annotations

from typing import Protocol


class VaultExporterPort(Protocol):
    """Outbound: read and write vault notes addressed by relative path."""

    def read_note(self, relative_path: str) -> str | None: ...

    def write_note(self, relative_path: str, content: str) -> None: ...

    def list_notes(self) -> list[str]: ...
