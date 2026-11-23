"""Outbound port for source connectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, cast


@dataclass(slots=True)
class ConnectorContext:
    client: Any
    limits: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))
    capabilities: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


@dataclass(slots=True)
class CollectedPage:
    title: str
    url: str
    content: str
    from_cache: bool = False
    raw: bytes | None = None
    content_type: str = ""
    metadata: dict[str, Any] = field(default_factory=lambda: cast(dict[str, Any], {}))


class SourceConnectorPort(Protocol):
    """Outbound: fetch/parse a source into collected pages."""

    name: str
    kinds: tuple[str, ...]

    def can_handle(self, source: dict[str, Any], ctx: ConnectorContext) -> bool: ...
    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]: ...
