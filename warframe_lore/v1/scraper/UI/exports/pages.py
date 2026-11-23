"""Normalize documents into generic structured RAG page records."""

from __future__ import annotations

import re
from typing import Any

from ...collect.wikitext import normalize_sections

_UNSAFE = re.compile(r"[^A-Za-z0-9À-ÿ_-]+")


def slug(value: str, fallback: str = "General") -> str:
    """Return a filesystem-safe, readable bucket or universe label."""
    cleaned = _UNSAFE.sub("_", str(value).strip())
    return cleaned.strip("_") or fallback


def bucket_title(doc: dict[str, Any]) -> str:
    """Choose the bucket label from category, then document type."""
    category = str(doc.get("category") or "").strip()
    if category:
        return category.split(",")[0].strip()
    return str(doc.get("docType") or "General").strip() or "General"


def page_record(doc: dict[str, Any]) -> dict[str, Any]:
    """Build the metadata + content record used by every structured export."""
    markdown = str(doc.get("content_markdown") or doc.get("content") or "")
    return {
        "page_title": str(doc.get("page_title") or doc.get("title") or ""),
        "category": bucket_title(doc),
        "last_updated": str(doc.get("last_updated") or ""),
        "language": str(doc.get("language") or "en"),
        "canon_status": str(doc.get("canon_status") or "canon"),
        "content_markdown": markdown,
        "sections": _sections(doc.get("sections")),
        "_source": str(doc.get("source_api") or doc.get("sourceId") or ""),
        "page_url": str(doc.get("page_url") or doc.get("url") or ""),
    }


def _sections(value: Any) -> list[dict[str, str]]:
    return normalize_sections(value)
