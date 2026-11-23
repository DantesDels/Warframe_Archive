"""JSON persistence for workshop settings."""

from __future__ import annotations

from pathlib import Path

from ..storage import read_json, write_json
from .models import Settings


class SettingsStore:
    """Load and save settings under the v1 data directory."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        payload = read_json(self.path, {})
        return Settings(
            min_relevance=int(payload.get("min_relevance", 60)),
            output_formats=tuple(payload.get("output_formats", ["json", "markdown"])),
            rag_coupling=bool(payload.get("rag_coupling", True)),
            max_pages_per_source=int(payload.get("max_pages_per_source", 25)),
            max_depth=int(payload.get("max_depth", 1)),
            same_host_only=bool(payload.get("same_host_only", True)),
            use_cache=bool(payload.get("use_cache", True)),
            incremental=bool(payload.get("incremental", True)),
            expand_manifests=bool(payload.get("expand_manifests", True)),
            max_manifest_urls=int(payload.get("max_manifest_urls", 50)),
            discovery_sitemaps=bool(payload.get("discovery_sitemaps", True)),
            discovery_feeds=bool(payload.get("discovery_feeds", True)),
            discovery_web_search=bool(payload.get("discovery_web_search", False)),
            discovery_web_search_url=str(payload.get("discovery_web_search_url", "")),
            discovery_git=bool(payload.get("discovery_git", False)),
            discovery_wiki=bool(payload.get("discovery_wiki", True)),
            discovery_seeds=tuple(
                str(x) for x in payload.get("discovery_seeds", []) if str(x).strip()
            ),
            discovery_max_candidates=int(payload.get("discovery_max_candidates", 30)),
            discovery_web_search_headers=_pairs(
                payload.get("discovery_web_search_headers")
            ),
            discovery_git_token=str(payload.get("discovery_git_token", "")),
            discovery_wiki_api_urls=tuple(
                str(url)
                for url in payload.get("discovery_wiki_api_urls", [])
                if str(url).strip()
            ),
            review_child_pages=bool(payload.get("review_child_pages", True)),
            use_playwright=bool(payload.get("use_playwright", False)),
            max_concurrency=int(payload.get("max_concurrency", 4)),
            per_host_concurrency=int(payload.get("per_host_concurrency", 2)),
            per_host_delay=float(payload.get("per_host_delay", 0.2)),
            max_retries=int(payload.get("max_retries", 2)),
            graph_enabled=bool(payload.get("graph_enabled", True)),
            graph_api_enabled=bool(payload.get("graph_api_enabled", False)),
            graph_api_host=str(payload.get("graph_api_host", "127.0.0.1")),
            graph_api_port=int(payload.get("graph_api_port", 8765)),
        )

    def save(self, settings: Settings) -> None:
        write_json(
            self.path,
            {
                "min_relevance": settings.min_relevance,
                "output_formats": list(settings.output_formats),
                "rag_coupling": settings.rag_coupling,
                "max_pages_per_source": settings.max_pages_per_source,
                "max_depth": settings.max_depth,
                "same_host_only": settings.same_host_only,
                "use_cache": settings.use_cache,
                "incremental": settings.incremental,
                "expand_manifests": settings.expand_manifests,
                "max_manifest_urls": settings.max_manifest_urls,
                "discovery_sitemaps": settings.discovery_sitemaps,
                "discovery_feeds": settings.discovery_feeds,
                "discovery_web_search": settings.discovery_web_search,
                "discovery_web_search_url": settings.discovery_web_search_url,
                "discovery_git": settings.discovery_git,
                "discovery_wiki": settings.discovery_wiki,
                "discovery_seeds": list(settings.discovery_seeds),
                "discovery_max_candidates": settings.discovery_max_candidates,
                "discovery_web_search_headers": [
                    list(pair) for pair in settings.discovery_web_search_headers
                ],
                "discovery_git_token": settings.discovery_git_token,
                "discovery_wiki_api_urls": list(settings.discovery_wiki_api_urls),
                "review_child_pages": settings.review_child_pages,
                "use_playwright": settings.use_playwright,
                "max_concurrency": settings.max_concurrency,
                "per_host_concurrency": settings.per_host_concurrency,
                "per_host_delay": settings.per_host_delay,
                "max_retries": settings.max_retries,
                "graph_enabled": settings.graph_enabled,
                "graph_api_enabled": settings.graph_api_enabled,
                "graph_api_host": settings.graph_api_host,
                "graph_api_port": settings.graph_api_port,
            },
        )


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    out: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            key, value = str(item[0]).strip(), str(item[1]).strip()
            if key:
                out.append((key, value))
        elif isinstance(item, dict):
            key = str(item.get("key", "")).strip()
            value = str(item.get("value", "")).strip()
            if key:
                out.append((key, value))
    return tuple(out)
