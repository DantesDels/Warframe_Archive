"""JSON persistence for workshop settings."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from ..storage import read_json, write_json
from .models import Settings

_DEFAULTS: dict[str, Any] = {
    "min_relevance": 60,
    "output_formats": ("json", "markdown"),
    "rag_coupling": True,
    "max_pages_per_source": 25,
    "max_depth": 1,
    "same_host_only": True,
    "use_cache": True,
    "incremental": True,
    "expand_manifests": True,
    "max_manifest_urls": 50,
    "allowed_languages": ("en",),
    "discovery_sitemaps": True,
    "discovery_feeds": True,
    "discovery_web_search": False,
    "discovery_web_search_url": "",
    "discovery_git": False,
    "discovery_wiki": True,
    "discovery_max_candidates": 30,
    "discovery_git_token": "",
    "review_child_pages": True,
    "use_playwright": False,
    "max_concurrency": 4,
    "per_host_concurrency": 2,
    "per_host_delay": 0.2,
    "max_retries": 2,
    "graph_enabled": True,
    "graph_api_enabled": False,
    "graph_api_host": "127.0.0.1",
    "graph_api_port": 8765,
}


class SettingsStore:
    """Load and save settings under the v1 data directory."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        p = read_json(self.path, {})
        langs = tuple(
            str(c).strip().lower()[:2]
            for c in p.get("allowed_languages", ["en"])
            if str(c).strip()
        ) or ("en",)
        seeds = tuple(str(x) for x in p.get("discovery_seeds", []) if str(x).strip())
        wikis = tuple(
            str(u) for u in p.get("discovery_wiki_api_urls", []) if str(u).strip()
        )
        return Settings(
            min_relevance=int(p.get("min_relevance", 60)),
            output_formats=tuple(p.get("output_formats", ["json", "markdown"])),
            rag_coupling=bool(p.get("rag_coupling", True)),
            max_pages_per_source=int(p.get("max_pages_per_source", 25)),
            max_depth=int(p.get("max_depth", 1)),
            same_host_only=bool(p.get("same_host_only", True)),
            use_cache=bool(p.get("use_cache", True)),
            incremental=bool(p.get("incremental", True)),
            expand_manifests=bool(p.get("expand_manifests", True)),
            max_manifest_urls=int(p.get("max_manifest_urls", 50)),
            allowed_languages=langs,
            discovery_sitemaps=bool(p.get("discovery_sitemaps", True)),
            discovery_feeds=bool(p.get("discovery_feeds", True)),
            discovery_web_search=bool(p.get("discovery_web_search", False)),
            discovery_web_search_url=str(p.get("discovery_web_search_url", "")),
            discovery_git=bool(p.get("discovery_git", False)),
            discovery_wiki=bool(p.get("discovery_wiki", True)),
            discovery_seeds=seeds,
            discovery_max_candidates=int(p.get("discovery_max_candidates", 30)),
            discovery_web_search_headers=_pairs(p.get("discovery_web_search_headers")),
            discovery_git_token=str(p.get("discovery_git_token", "")),
            discovery_wiki_api_urls=wikis,
            review_child_pages=bool(p.get("review_child_pages", True)),
            use_playwright=bool(p.get("use_playwright", False)),
            max_concurrency=int(p.get("max_concurrency", 4)),
            per_host_concurrency=int(p.get("per_host_concurrency", 2)),
            per_host_delay=float(p.get("per_host_delay", 0.2)),
            max_retries=int(p.get("max_retries", 2)),
            graph_enabled=bool(p.get("graph_enabled", True)),
            graph_api_enabled=bool(p.get("graph_api_enabled", False)),
            graph_api_host=str(p.get("graph_api_host", "127.0.0.1")),
            graph_api_port=int(p.get("graph_api_port", 8765)),
        )

    def save(self, settings: Settings) -> None:
        raw = asdict(settings)
        list_keys = (
            "output_formats", "discovery_seeds",
            "discovery_wiki_api_urls", "allowed_languages",
        )
        for key in list_keys:
            raw[key] = list(raw.get(key) or ())
        raw["discovery_web_search_headers"] = [
            list(pair) for pair in settings.discovery_web_search_headers
        ]
        write_json(self.path, raw)


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        return ()
    out: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            k, v = str(item[0]).strip(), str(item[1]).strip()
        elif isinstance(item, dict):
            k, v = str(item.get("key", "")).strip(), str(item.get("value", "")).strip()
        else:
            continue
        if k:
            out.append((k, v))
    return tuple(out)
