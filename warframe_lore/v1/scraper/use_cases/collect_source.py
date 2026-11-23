"""Use case: collect one source through connector + pipeline."""

from __future__ import annotations

import hashlib
import time
from typing import Any, cast

from ..collect.adapters import collect_pages
from ..ports.outbound.sources import CollectedPage
from .pipeline.base import PipelineContext, PipelineItem
from .pipeline.default import default_pipeline

MAX_TEXT = 200_000


def collect_source(
    source: dict[str, Any],
    uid: str,
    client: Any,
    limits: dict[str, Any],
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, str]]]:
    loc = str(source.get("location", "")).strip()
    limits.setdefault("connector_state", state.setdefault("_connector_state", {}))
    try:
        pages = cast(list[CollectedPage], collect_pages(source, client, limits))
    except Exception as exc:  # noqa: BLE001
        return [], [f"{loc}: {exc}"], []
    ctx = PipelineContext(source=source, universe_id=uid, settings=limits)
    raw: list[PipelineItem] = [PipelineItem(page=p) for p in pages]
    accepted = default_pipeline().run(list(raw), ctx)
    rejected = [i for i in raw if not i.accepted]
    docs: list[dict[str, Any]] = []
    errors: list[str] = []
    updates: list[dict[str, str]] = []
    for item in rejected:
        if item.reason and item.reason != "duplicate_url":
            errors.append(f"{item.page.url}: {item.reason}")
    for item in accepted:
        page = item.page
        text = str(page.content)[:MAX_TEXT]
        metadata = _metadata(page)
        digest = str(metadata.get("contentHash") or "") or hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest()
        prev = state.get(page.url) if bool(limits.get("incremental")) else None
        prev_hash = (
            str(cast(dict[str, Any], prev).get("hash", ""))
            if isinstance(prev, dict)
            else ""
        )
        if prev_hash == digest and prev_hash:
            continue
        docs.append(_doc(source, uid, page, text, digest))
        updates.append({"url": str(page.url), "hash": digest, "title": str(page.title)})
    pending = cast(list[dict[str, str]], limits.get("pending_child_urls", []))
    if pending:
        updates.extend({"url": p["url"], "hash": "",
            "title": f"child:{p['parent']}"} for p in pending)
    return docs, errors, updates


def _metadata(page: CollectedPage) -> dict[str, Any]:
    """Return the optional connector metadata as a typed mapping."""
    return cast(dict[str, Any], getattr(page, "metadata", None) or {})


def _doc(
    src: dict[str, Any], uid: str, page: CollectedPage, text: str, digest: str
) -> dict[str, Any]:
    metadata = _metadata(page)
    return {
        "id": _doc_id(src),
        "universeId": uid,
        "sourceId": src.get("id"),
        "title": str(page.title)[:180],
        "url": str(page.url),
        "docType": str(metadata.get("docType") or src.get("kind", "website")),
        "language": str(
            metadata.get("language") or _guess_lang(str(page.url), text)
        ),
        "relevance": float(src.get("score", 1.0) or 1.0),
        "isDuplicate": False,
        "excerpt": text[:320],
        "content": text,
        "contentHash": digest,
        "fromCache": bool(getattr(page, "from_cache", False)),
    }


def _doc_id(source: dict[str, Any]) -> str:
    base = str(source.get("id", "src"))
    return f"doc-{base}-{int(time.time() * 1000) % 100000}-{time.time_ns() % 10000}"


def _guess_lang(url: str, text: str) -> str:
    low = url.lower()
    if "/fr" in low or "fr.wiki" in low or ".fr/" in low:
        return "fr"
    if "/en" in low or "wiki.warframe.com" in low:
        return "en"
    return "fr" if any(ch in text[:2000] for ch in "àâçéèêëîïôûùüÿœæ") else "en"
