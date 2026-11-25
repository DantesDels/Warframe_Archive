"""Compatibility facade over pluggable connectors."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from ..connectors.base import CollectedPage, ConnectorContext
from ..connectors.registry import default_registry
from ..observability.progress import current_reporter, stop_requested
from .binary_text import looks_binary
from .crawl_filter import (
    is_generalist_domain,
    keep_crawl_url,
    matches_universe_topic,
)
from .language import canonical_locale_url_key
from .manifest import extract_manifest_urls

_REGISTRY = default_registry()


def collect_pages(
    source: dict[str, Any], client: Any, limits: dict[str, Any]
) -> list[CollectedPage]:
    ctx = ConnectorContext(client=client, limits=limits)
    pages = _REGISTRY.resolve(source, ctx).collect(source, ctx)
    if limits.get("expand_manifests"):
        is_lzma = str(source.get("location", "")).lower().endswith(".lzma")
        review = False if is_lzma else bool(limits.get("review_child_pages", True))
        manifest_base = str(source.get("manifest_base_url") or "")
        pages = _expand(pages, ctx, review=review, manifest_base=manifest_base)
    return pages


def _expand(
    pages: list[CollectedPage],
    ctx: ConnectorContext,
    *,
    review: bool = True,
    manifest_base: str = "",
) -> list[CollectedPage]:
    out = list(pages)
    pending = cast(
        list[dict[str, str]], ctx.limits.setdefault("pending_child_urls", [])
    )
    seen = {canonical_locale_url_key(p.url) for p in out} | {
        canonical_locale_url_key(str(item.get("url", ""))) for item in pending
    }
    same_host = bool(ctx.limits.get("same_host_only", True))
    langs = ctx.limits.get("allowed_languages")
    u_kw = list(
        ctx.limits.get("universe_keywords") or ctx.limits.get("topic_tags") or []
    )
    budget = max(0, int(ctx.limits.get("max_manifest_urls", 50)))
    if review:
        per_src = max(0, int(ctx.limits.get("max_pending_children_per_source", 100)))
        budget = min(budget, max(0, per_src - len(pending)))
    reporter = current_reporter(ctx.limits)
    for page in pages:
        if stop_requested(ctx.limits) or budget <= 0:
            break
        content = str(page.content)
        base_ref = manifest_base.strip() or page.url
        base_host = (urlparse(base_ref).hostname or "").lower().removeprefix("www.")
        gen_base = is_generalist_domain(base_ref)
        if gen_base:
            continue
        children = (
            [] if looks_binary(content)
            else extract_manifest_urls(
                content, page.url, limit=budget * 3, manifest_base=manifest_base
            )
        )
        if children:
            reporter.manifest(len(children))
        for child in children:
            if stop_requested(ctx.limits):
                break
            c_host = (urlparse(child).hostname or "").lower().removeprefix("www.")
            same_root = ".".join(c_host.split(".")[-2:]) == ".".join(
                base_host.split(".")[-2:]
            )
            if same_host and base_host and c_host and not same_root:
                continue
            if (gen_base or is_generalist_domain(child)) and (
                not u_kw or not matches_universe_topic(child, "", u_kw)
            ):
                continue
            if not keep_crawl_url(child, base_ref, allowed_languages=langs):
                continue
            norm = canonical_locale_url_key(child)
            if not norm or norm in seen or budget <= 0:
                continue
            seen.add(norm)
            budget -= 1
            if review:
                pending.append({"url": child, "parent": page.url})
            else:
                out.extend(_collect_child(child, ctx))
            if budget <= 0:
                break
    return out


def _collect_child(url: str, ctx: ConnectorContext) -> list[CollectedPage]:
    source: dict[str, Any] = {"location": url, "kind": "website"}
    limits: dict[str, Any] = {
        **ctx.limits,
        "max_pages_per_source": 1,
        "max_depth": 0,
        "expand_manifests": False,
    }
    try:
        child_ctx = ConnectorContext(client=ctx.client, limits=limits)
        return _REGISTRY.resolve(source, child_ctx).collect(source, child_ctx)
    except Exception:
        return []
