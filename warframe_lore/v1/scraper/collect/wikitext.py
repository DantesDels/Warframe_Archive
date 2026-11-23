"""Generic wikitext-to-Markdown cleaning and section splitting for RAG."""

from __future__ import annotations

import re
from typing import Any

from .language import detect_language

_HEADING = re.compile(r"^(={2,6})\s*(.+?)\s*\1\s*$")
_BULLET = re.compile(r"^(\*+)\s*(.+)$")
_TEMPLATE = re.compile(r"\{\{([^{}]*)\}\}")
_FILE_OR_CAT = re.compile(
    r"\[\[(?:File|Fichier|Image|Media|Category|Catégorie|Categorie):[^\]]*\]\]",
    re.I,
)
_INTERNAL_LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
_EXTERNAL_LINK = re.compile(r"\[(https?://[^\s\]]+)\s+([^\]]+)\]")
_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^>]*/?>", re.S | re.I)
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_CATEGORIES = re.compile(
    r"\[\[(?:Category|Catégorie|Categorie):([^\]|]+)(?:\|[^\]]*)?\]\]", re.I
)
_SPECULATION = (
    "fanon",
    "non-canon",
    "non canon",
    "speculation",
    "hors canon",
)
_DROP_TEMPLATES = frozenset({
    "infobox", "navbox", "cite", "reflist", "references", "main", "see also",
    "gallery", "stub", "cleanup", "toc", "clear", "documentation", "module",
    "portal", "quotebox", "hatnote", "distinguish", "about", "redirect",
})


def wikitext_to_markdown(text: str) -> str:
    """Convert generic wiki markup to clean, chunkable Markdown."""
    lines: list[str] = []
    for raw in str(text).splitlines():
        line = raw.strip()
        if not line or line.startswith(("|", "!", "{|", "|}", "|-")):
            continue
        heading = _HEADING.match(line)
        if heading:
            lines.append(f"{'#' * len(heading.group(1))} {heading.group(2)}")
            continue
        line = _clean_inline(line)
        if not line:
            continue
        bullet = _BULLET.match(line)
        if bullet:
            pad = "  " * (len(bullet.group(1)) - 1)
            lines.append(f"{pad}- {bullet.group(2).strip()}")
        else:
            lines.append(line)
    return "\n".join(lines).strip()


def split_sections(page_title: str, markdown: str) -> list[dict[str, str]]:
    """Split Markdown into RAG chunks keyed by level-two headings."""
    sections: list[dict[str, str]] = []
    current, buffer = "", []
    for line in markdown.splitlines():
        if line.startswith("## "):
            sections.append(_section(page_title, current, buffer))
            current, buffer = line[3:].strip(), []
        else:
            buffer.append(line)
    sections.append(_section(page_title, current, buffer))
    return [s for s in sections if s["contenu"] or s["section"]]


def normalize_sections(value: Any) -> list[dict[str, str]]:
    """Normalize legacy or malformed section lists into typed records."""
    if not isinstance(value, list):
        return []
    return [
        _section(
            str(r.get("titre_page", "") or ""),
            str(r.get("section", "") or ""),
            str(r.get("contenu", "") or "").splitlines(),
        )
        for item in value
        for r in (item if isinstance(item, dict) else {},)
    ]


def canon_status(title: str, categories: list[str], text: str) -> str:
    """Flag speculative pages generically, without universe-specific rules."""
    sample = " ".join([title, " ".join(categories), text[:1000]]).lower()
    return "speculation" if any(word in sample for word in _SPECULATION) else "canon"


def categories_from_wikitext(text: str) -> list[str]:
    """Collect inline category links from wikitext."""
    return [match.strip() for match in _CATEGORIES.findall(str(text))]


def page_metadata(
    title: str, url: str, api: str, categories: list[str],
    touched: str, revid: str, markdown: str, wikitext: str,
) -> dict[str, Any]:
    """Build the generic structured record consumed by exports and RAG."""
    labels = list(dict.fromkeys(list(categories) + categories_from_wikitext(wikitext)))
    return {
        "page_title": title, "category": ", ".join(labels), "categories": labels,
        "last_updated": touched, "language": detect_language(url, markdown),
        "canon_status": canon_status(title, labels, markdown),
        "content_markdown": markdown, "sections": split_sections(title, markdown),
        "page_url": url, "_source": api, "source_api": api,
        "touched": touched, "revid": revid,
    }


def _clean_inline(line: str) -> str:
    line = _FILE_OR_CAT.sub("", _HTML_COMMENT.sub("", _REF.sub("", line)))
    for _ in range(5):
        nxt = _TEMPLATE.sub(_template_text, line)
        if nxt == line:
            break
        line = nxt
    line = _INTERNAL_LINK.sub(lambda m: (m.group(2) or m.group(1)).strip(), line)
    line = _EXTERNAL_LINK.sub(lambda m: f"{m.group(2)} ({m.group(1)})", line)
    return " ".join(line.replace("'''", "").replace("''", "").split()).strip()


def _template_text(match: re.Match[str]) -> str:
    parts = [p.strip() for p in match.group(1).split("|")]
    if not parts or not parts[0]:
        return ""
    name = parts[0].lower()
    is_meta = any(name.startswith(d) for d in _DROP_TEMPLATES)
    if is_meta or any("=" in p for p in parts[1:]):
        return ""
    pos = [p for p in parts[1:] if p and not p.startswith("#")]
    if len(pos) == 1:
        return pos[0]
    return pos[1] if len(pos) == 2 and len(pos[1]) <= 60 else ""


def _section(title: str, heading: str, lines: list[str]) -> dict[str, str]:
    body = "\n".join(lines).strip()
    return {"titre_page": str(title), "section": heading, "contenu": body}
