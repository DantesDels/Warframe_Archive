"""Source collection helpers for execution worker."""

from __future__ import annotations

import hashlib
import time

from ..collect.adapters import collect_pages
from ..collect.http import HttpClient

MAX_TEXT = 200_000


def collect_source(
    source: dict, universe_id: str, client: HttpClient, limits: dict, state: dict
):
    """Collect one or more documents from a source with incremental state."""
    loc = str(source.get("location", "")).strip()
    kind = str(source.get("kind", "website"))
    try:
        pages = collect_pages(source, client, limits)
    except Exception as exc:  # noqa: BLE001
        return [], [f"{loc}: {exc}"], []
    docs: list[dict] = []
    errors: list[str] = []
    updates: list[dict] = []
    for page in pages:
        text = _normalize(page.content)[:MAX_TEXT]
        if not text:
            errors.append(f"{page.url}: contenu vide")
            continue
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        prev = state.get(page.url) if limits.get("incremental") else None
        if prev and prev.get("hash") == content_hash:
            continue
        doc = _doc(source, universe_id, kind, page.title, page.url, text, content_hash)
        doc["fromCache"] = bool(page.from_cache)
        docs.append(doc)
        updates.append({"url": page.url, "hash": content_hash, "title": page.title})
    if not docs and not errors and not limits.get("incremental"):
        errors.append(f"{loc}: aucun document collect\xC3\xA9")
    return docs, errors, updates


def _doc(src: dict, uid: str, kind: str, title: str, url: str, text: str, digest: str):
    return {
        "id": _doc_id(src),
        "universeId": uid,
        "sourceId": src.get("id"),
        "title": title[:180],
        "url": url,
        "docType": kind,
        "language": _guess_lang(url, text),
        "relevance": float(src.get("score", 1.0)),
        "isDuplicate": False,
        "excerpt": text[:320],
        "content": text,
        "contentHash": digest,
    }


def _doc_id(source: dict) -> str:
    base = source.get("id", "src")
    return f"doc-{base}-{int(time.time()*1000)%100000}-{time.time_ns()%10000}"


def _normalize(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "").splitlines()]
    return "\n".join(line for line in lines if line)


def _guess_lang(url: str, text: str) -> str:
    low = url.lower()
    if "/fr" in low or "fr.wiki" in low or ".fr/" in low:
        return "fr"
    if "/en" in low or "wiki.warframe.com" in low:
        return "en"
    sample = text[:2000]
    french = "\xE0\xE2\xE9\xE8\xEA\xEB\xEE\xEF\xF4\xF9\xFB\xE7"
    return "fr" if any(ch in sample for ch in french) else "en"
