"""Normalize documents into generic structured RAG page records."""

from __future__ import annotations

import re
from typing import Any

from ...collect.wikitext import normalize_sections

_UNSAFE = re.compile(r"[^A-Za-z0-9À-ÿ_-]+")
_NOISE_CATS = (
    "births", "deaths", "articles with", "articles using", "all article",
    "short description", "disambiguation", "use mdy", "use dmy",
    "use american", "living people", "stubs", "pages using", "cs1",
    "wikidata", "infobox", "official website", "male actors", "voice actors",
    "emigrants", "award winners", "musical groups", "video games",
    "windows games", "playstation", "deprecated", "template", "updateme",
)


def slug(value: str, fallback: str = "General") -> str:
    """Return a filesystem-safe, readable bucket or universe label."""
    cleaned = _UNSAFE.sub("_", str(value).strip())
    return cleaned.strip("_") or fallback


def bucket_title(doc: dict[str, Any]) -> str:
    """Choose a semantic lore bucket label from category, title, URL and docType."""
    raw_cat = str(doc.get("category") or "").strip()
    title = str(doc.get("page_title") or doc.get("title") or "").strip()
    url = str(doc.get("page_url") or doc.get("url") or "").lower()
    api = str(doc.get("source_api") or "").lower()
    t_low = title.lower()
    cats = [
        c.strip() for c in raw_cat.split(",")
        if c.strip() and not any(n in c.lower() for n in _NOISE_CATS)
    ]
    c_low = " | ".join(c.lower() for c in cats)
    is_wf = (
        "warframe" in url or "warframe" in api
        or "tennocon" in url or raw_cat.startswith("Export")
    )
    if is_wf:
        if "/transcript" in t_low:
            return "Lore_Dialogues_Quetes"
        if "kinemantik" in t_low or "fables & frontiers" in t_low or "/kim" in t_low:
            return "Lore_Dialogues_KIM"
        if "/quotes" in t_low or "/citations" in t_low:
            return "Lore_Dialogues_Quotes"
        if "fragment" in t_low or "fragment" in c_low:
            return "Lore_Fragments"
        if "quest" in c_low or "quêtes" in c_low:
            return "Lore_Quetes"
        if "character" in c_low or "personnages" in c_low:
            return "Lore_Characters"
        fac_keys = ("faction", "enemies", "codex", "weapons", "export")
        if any(k in c_low for k in fac_keys):
            return "Lore_Cosmologie_Factions"
        if (
            "lore" in c_low or "story" in c_low or "history" in c_low
            or "quotes" in c_low or "wiki." in url or "wikipedia.org" in url
        ):
            return "Lore_Univers_Histoire"
        if "warframe.com" in url or "tennocon.com" in url:
            return "Lore_Site_Officiel"
    if cats:
        return cats[0]
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
