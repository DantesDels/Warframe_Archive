"""Outbound ports for the graph engine stage.

The LLM port is reused as-is from the scraper hexagon so any compatible
adapter (local LM Studio or remote API) can drive the Map phase.
"""

from __future__ import annotations

from typing import Protocol

from ..scraper.ports.outbound.llm import LlmPort, LlmRequest, LlmResponse
from .graph import KnowledgeGraph
from .models import ExtractedBatch

__all__ = ["GraphStorePort", "LlmPort", "LlmRequest", "LlmResponse"]


class GraphStorePort(Protocol):
    """Outbound: persist the graph, the Map cache and the chunk manifest."""

    def load_graph(self) -> KnowledgeGraph: ...

    def save_graph(self, graph: KnowledgeGraph) -> None: ...

    def load_manifest(self) -> dict[str, str]: ...

    def save_manifest(self, manifest: dict[str, str]) -> None: ...

    def load_extraction(self, chunk_id: str) -> ExtractedBatch | None: ...

    def save_extraction(self, chunk_id: str, batch: ExtractedBatch) -> None: ...
