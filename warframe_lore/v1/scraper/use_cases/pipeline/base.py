"""Pipeline contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, cast


@dataclass(slots=True)
class PipelineContext:
    source: dict[str, Any]
    universe_id: str
    settings: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    capabilities: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any],
        {}))


@dataclass(slots=True)
class PipelineItem:
    page: Any
    document: dict[str, Any] | None = None
    accepted: bool = True
    reason: str = ""


class Stage(Protocol):
    name: str

    def run(self, items: list[PipelineItem],
            ctx: PipelineContext) -> list[PipelineItem]: ...
