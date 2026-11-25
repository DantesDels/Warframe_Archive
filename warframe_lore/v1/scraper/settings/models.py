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
    use_cache: bool = True
    incremental: bool = True
    expand_manifests: bool = True
    max_manifest_urls: int = 50
    max_pending_children_per_source: int = 100
    max_pending_children_per_run: int = 1000
    allowed_languages: tuple[str, ...] = ("en",)
    discovery_sitemaps: bool = True
    discovery_feeds: bool = True
    discovery_web_search: bool = False
    discovery_web_search_url: str = ""
    discovery_git: bool = False
    discovery_wiki: bool = True
    discovery_seeds: tuple[str, ...] = ()
    discovery_max_candidates: int = 30
    discovery_web_search_headers: tuple[tuple[str, str], ...] = ()
    discovery_git_token: str = ""
    discovery_wiki_api_urls: tuple[str, ...] = ()
    review_child_pages: bool = True
    use_playwright: bool = False
    max_concurrency: int = 4
    per_host_concurrency: int = 2
    per_host_delay: float = 0.2
    max_retries: int = 2
    graph_enabled: bool = True
    graph_api_enabled: bool = False
    graph_api_host: str = "127.0.0.1"
    graph_api_port: int = 8765

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
        if self.max_manifest_urls < 1:
            raise ValueError("max_manifest_urls must be >= 1")
        if self.discovery_max_candidates < 1:
            raise ValueError("discovery_max_candidates must be >= 1")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be >= 1")
        if self.per_host_concurrency < 1:
            raise ValueError("per_host_concurrency must be >= 1")
        if self.per_host_delay < 0:
            raise ValueError("per_host_delay must be >= 0")
        if self.max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if not 1 <= self.graph_api_port <= 65535:
            raise ValueError("graph_api_port must be between 1 and 65535")
        if not self.graph_api_host.strip():
            raise ValueError("graph_api_host must not be empty")


@dataclass(frozen=True, slots=True)
class LaunchPlan:
    """Validated choices collected by the pre-execution dialog."""

    settings: Settings
    universe_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.universe_ids:
            raise ValueError("at least one Universe is required")
