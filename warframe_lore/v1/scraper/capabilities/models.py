"""Capability configuration persisted per universe."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CrawlBudget:
    max_pages: int = 25
    max_depth: int = 1
    same_host_only: bool = True
    max_manifest_urls: int = 50
    max_concurrency: int = 4
    per_host_concurrency: int = 2
    per_host_delay: float = 0.2
    max_retries: int = 2


@dataclass(slots=True)
class RagBudget:
    enabled: bool = False
    chunk_size: int = 800
    chunk_overlap: int = 120
    vector_format: str = "jsonl"


@dataclass(slots=True)
class WatchBudget:
    enabled: bool = False
    poll_minutes: int = 60
    backoff_minutes: int = 15


@dataclass(slots=True)
class LlmBudget:
    enabled: bool = False
    provider: str = "openai-compatible"
    model: str = ""
    endpoint: str = "http://127.0.0.1:1234/v1"
    max_tokens: int = 2048
    max_calls: int = 20
    vram_gb: float = 0.0


@dataclass(slots=True)
class MultimodalBudget:
    enabled: bool = False
    ocr: bool = False
    asr: bool = False
    vision: bool = False
    max_file_mb: int = 20
    max_media_minutes: int = 30


@dataclass(slots=True)
class UniverseCapabilities:
    crawl: CrawlBudget = field(default_factory=CrawlBudget)
    rag: RagBudget = field(default_factory=RagBudget)
    watch: WatchBudget = field(default_factory=WatchBudget)
    active_learning: LlmBudget = field(default_factory=lambda: LlmBudget(enabled=False))
    graph_rag: LlmBudget = field(default_factory=lambda: LlmBudget(enabled=False))
    fact_check: LlmBudget = field(default_factory=lambda: LlmBudget(enabled=False))
    multimodal: MultimodalBudget = field(default_factory=MultimodalBudget)
    self_heal: LlmBudget = field(default_factory=lambda: LlmBudget(enabled=False))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> UniverseCapabilities:
        data = payload or {}
        return cls(
            crawl=CrawlBudget(**data.get("crawl", {})),
            rag=RagBudget(**data.get("rag", {})),
            watch=WatchBudget(**data.get("watch", {})),
            active_learning=LlmBudget(**data.get("active_learning", {})),
            graph_rag=LlmBudget(**data.get("graph_rag", {})),
            fact_check=LlmBudget(**data.get("fact_check", {})),
            multimodal=MultimodalBudget(**data.get("multimodal", {})),
            self_heal=LlmBudget(**data.get("self_heal", {})),
        )


def default_capabilities() -> dict[str, Any]:
    return UniverseCapabilities().to_dict()
