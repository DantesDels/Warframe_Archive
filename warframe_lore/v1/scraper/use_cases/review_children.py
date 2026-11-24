"""Human-in-the-loop child page/manifest review with SPA & authority scoring."""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from ..collect.crawl_filter import infer_path_prefix, keep_crawl_url
from ..collect.html_extract import extract_links
from ..collect.http import HttpClient, browser_headers
from ..collect.manifest import extract_manifest_urls
from ..collect.spa import looks_like_spa, playwright_available, render_spa_page
from ..discovery.models import Candidate
from .child_scoring import child_authority_score


def preview_child_candidates(
    workspace: Any,
    universe: dict[str, Any],
    location: str,
    *,
    client: Any | None = None,
    limit: int = 250,
    use_playwright: bool = False,
) -> list[dict[str, Any]]:
    """Discover child links (static HTML, manifest or SPA/JS) with parent authority."""
    http = client or HttpClient()
    resp = http.get(location, headers=browser_headers(), use_cache=True)
    body = bytes(getattr(resp, "content", b""))
    text = body.decode(getattr(resp, "encoding", None) or "utf-8", errors="replace")
    final_url = str(getattr(resp, "url", location) or location)
    ctype = str((getattr(resp, "headers", None) or {}).get("content-type", "")).lower()
    is_html = "html" in ctype or "<html" in text[:400].lower()
    urls = _extract_child_urls(
        text, final_url, is_html=is_html, limit=limit, use_playwright=use_playwright
    )
    uid = str(universe["id"])
    existing = {
        str(c.get("location", "")).rstrip("/").lower()
        for c in cast(list[dict[str, Any]], workspace.candidates_for(uid))
    }
    out: list[dict[str, Any]] = []
    for idx, url in enumerate(urls):
        key = url.rstrip("/").lower()
        if key in existing:
            continue
        existing.add(key)
        score, breakdown = child_authority_score(workspace, uid, final_url, url)
        cand = Candidate(
            id=f"child-{abs(hash((uid, key, idx))) % 1000000}",
            universe_id=uid, kind="website", location=url,
            title=f"Page enfant: {url.rsplit('/', 1)[-1] or url}",
            score=score, proof=f"Page enfant détectée depuis {final_url}",
            discovered_by="manifest_review", status="proposed",
            score_breakdown=breakdown,
            metadata={"parent_location": final_url, "needs_review": True},
        )
        out.append(_payload(cand))
    if out:
        merged = cast(list[dict[str, Any]], workspace.data.get("candidates", []))
        merged.extend(out)
        workspace.data["candidates"] = merged
        workspace.save()
    return out


def _extract_child_urls(
    text: str, final_url: str, *, is_html: bool, limit: int, use_playwright: bool
) -> list[str]:
    if not is_html:
        return extract_manifest_urls(text, final_url, limit=limit)
    static_links = _scope_html_links(extract_links(text, final_url), final_url)
    should_render = use_playwright or (
        playwright_available() and looks_like_spa(text, len(static_links))
    )
    if should_render:
        try:
            rendered = render_spa_page(final_url)
            spa_links = _scope_html_links(rendered.links, rendered.final_url)
            if len(spa_links) > len(static_links):
                return spa_links[:limit]
        except Exception:  # noqa: BLE001
            pass
    return (static_links or extract_manifest_urls(text, final_url, limit=limit))[:limit]


def _scope_html_links(links: list[str], parent_url: str) -> list[str]:
    parent = urlparse(parent_url)
    parent_host = (parent.hostname or "").lower()
    parent_path = parent.path.rstrip("/").lower()
    parent_norm = parent_url.rstrip("/").lower()
    prefix = infer_path_prefix(parent_url)
    same_section, other, seen = [], [], set()
    for url in links:
        norm = url.rstrip("/").lower()
        if not norm or norm == parent_norm or norm in seen:
            continue
        parsed = urlparse(url)
        if (parsed.hostname or "").lower() != parent_host:
            continue
        if not keep_crawl_url(url, parent_url, prefix=prefix):
            continue
        seen.add(norm)
        path = parsed.path.rstrip("/").lower()
        in_sec = bool(parent_path) and path.startswith(f"{parent_path}/")
        (same_section if in_sec else other).append(url)
    return same_section or other


def _payload(item: Candidate) -> dict[str, Any]:
    return {
        "id": item.id, "universeId": item.universe_id, "kind": item.kind,
        "location": item.location, "title": item.title, "score": item.score,
        "proof": item.proof, "discoveredBy": item.discovered_by,
        "status": item.status, "forceUpdate": item.force_update,
        "scoreBreakdown": dict(item.score_breakdown),
        "metadata": dict(item.metadata),
    }
