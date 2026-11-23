"""Compatibility facade over pluggable connectors."""

from __future__ import annotations

from typing import Any, cast

from ..connectors.base import CollectedPage, ConnectorContext
from ..connectors.registry import default_registry
from .manifest import extract_manifest_urls

_REGISTRY = default_registry()


def collect_pages(
    source: dict[str, Any], client: Any, limits: dict[str, Any]
) -> list[CollectedPage]:
    ctx = ConnectorContext(client=client, limits=limits)
    pages = _REGISTRY.resolve(source, ctx).collect(source, ctx)
    if limits.get("expand_manifests"):
        review = bool(limits.get("review_child_pages", True))
        pages = _expand(pages, ctx, review=review)
    return pages


def _expand(
    pages: list[CollectedPage], ctx: ConnectorContext, *, review: bool = True
) -> list[CollectedPage]:
    out = list(pages)
    seen = {p.url.rstrip("/") for p in out}
    budget = max(0, int(ctx.limits.get("max_manifest_urls", 50)))
    pending = cast(list[dict[str, str]], ctx.limits.setdefault("pending_child_urls",
        []))
    for page in pages:
        for child in extract_manifest_urls(page.content, page.url, limit=budget):
            norm = child.rstrip("/")
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
