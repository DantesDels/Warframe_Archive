"""Execution settings and launch plan for the v1 ingestion workshop."""

from __future__ import annotations

from dataclasses import dataclass

OUTPUT_FORMATS = ("json", "jsonl", "csv", "markdown", "sql", "nosql")


@dataclass(frozen=True, slots=True)
class Settings:
    """Defaults applied to every discovery and execution."""

    min_relevance: int = 60
    output_formats: tuple[str, ...] = ("json", "markdown")
    rag_coupling: bool = True
    max_pages_per_source: int = 25
    max_depth: int = 1
    same_host_only: bool = True

    def __post_init__(self) -> None:
        if not 0 <= self.min_relevance <= 100:
            raise ValueError("min_relevance must be between 0 and 100")
        if not self.output_formats:
            raise ValueError("at least one output format is required")
        unknown = set(self.output_formats) - set(OUTPUT_FORMATS)
        if unknown:
            raise ValueError(f"unsupported output formats: {sorted(unknown)}")
        if self.max_pages_per_source < 1:
            raise ValueError("max_pages_per_source must be >= 1")
        if self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    """Validated choices collected by the pre-execution dialog."""

    settings: Settings
    universe_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.universe_ids:
            raise ValueError("at least one Universe is required")
