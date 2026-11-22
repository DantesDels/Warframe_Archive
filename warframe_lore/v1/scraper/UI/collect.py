"""Source collection helpers for execution worker."""

from __future__ import annotations

import time

from ..collect.adapters import collect_pages
from ..collect.http import HttpClient

MAX_TEXT = 200_000


def collect_source(source: dict, universe_id: str, client: HttpClient, limits: dict):
    """Collect one or more documents from a source."""
    loc = str(source.get("location", "")).strip()
    kind = str(source.get("kind", "website"))
    try:
        pages = collect_pages(source, client, limits)
    except Exception as exc:  # noqa: BLE001
        return [], [f"{loc}: {exc}"]
    docs: list[dict] = []
    errors: list[str] = []
    for page in pages:
        text = _normalize(page.content)[:MAX_TEXT]
        if not text:
            errors.append(f"{page.url}: contenu vide")
            continue
        docs.append(_doc(source, universe_id, kind, page.title, page.url, text))
    if not docs and not errors:
        errors.append(f"{loc}: aucun document collectÃ©")
    return docs, errors


def _doc(source: dict, universe_id: str, kind: str, title: str, url: str, text: str):
    return {
        "id": _doc_id(source),
        "universeId": universe_id,
        "sourceId": source.get("id"),
        "title": title[:180],
        "url": url,
        "docType": kind,
        "language": _guess_lang(url, text),
        "relevance": float(source.get("score", 1.0)),
        "isDuplicate": False,
        "excerpt": text[:320],
        "content": text,
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
    return "fr" if any(ch in sample for ch in "àâéèêëîïôùûç") else "en"
