"""Discovery providers."""

from __future__ import annotations

from typing import Any

from .keyword import KeywordProvider


def build_default_providers(settings: dict[str, Any] | None = None) -> list[Any]:
    cfg = settings or {}
    client = cfg.get("http_client")
    providers: list[Any] = [KeywordProvider()]
    if bool(cfg.get("discovery_web_search", False)):
        from .web_search import WebSearchProvider

        headers = {
            str(key): str(value)
            for key, value in (cfg.get("discovery_web_search_headers") or [])
            if str(key).strip()
        }
        endpoint = str(cfg.get("discovery_web_search_url", ""))
        providers.append(WebSearchProvider(endpoint, headers=headers))
    if bool(cfg.get("discovery_sitemaps", True)):
        from .sitemap import SitemapProvider

        providers.append(SitemapProvider(client=client))
    if bool(cfg.get("discovery_feeds", True)):
        from .feed import FeedProvider

        providers.append(FeedProvider(client=client))
    if bool(cfg.get("discovery_git", False)):
        from .git import GitProvider

        providers.append(GitProvider(token=str(cfg.get("discovery_git_token", ""))))
    if bool(cfg.get("discovery_wiki", True)):
        from .wiki import WikiProvider

        api_urls = tuple(
            str(url)
            for url in cfg.get("discovery_wiki_api_urls", [])
            if str(url).strip()
        )
        providers.append(WikiProvider(api_urls=api_urls))
    return providers


__all__ = ["KeywordProvider", "build_default_providers"]
