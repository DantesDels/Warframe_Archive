"""DOM-based HTML cleaning for LLM/RAG-ready text and Markdown."""

from __future__ import annotations

import re
from typing import Any

try:
    from bs4 import BeautifulSoup, Comment
except ImportError:  # pragma: no cover - optional dependency
    BeautifulSoup = None  # type: ignore[assignment,misc]
    Comment = ()  # type: ignore[assignment,misc]

SKIP_TAGS = frozenset({
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "template", "svg", "iframe", "canvas", "form", "button", "select",
})
INLINE_UNWRAP_TAGS = (
    "span", "strong", "b", "em", "i", "small", "mark", "time", "abbr", "font",
)
CONTENT_SELECTORS = (".mw-parser-output", "main", "article", '[role="main"]')
CHROME_TOKENS = (
    "rlconf", "optanon", "rollbar", "mw-notification", "mw-head",
    "vector-menu", "sidebar", "sitenotice", "cookie", "banner", "advert",
)
JUNK_MARKERS = (
    "RLCONF", "_rollbarConfig", "OptanonWrapper", "mw.config.set",
    "window.RLQ", "function(){", "=> {",
)


def has_beautifulsoup() -> bool:
    """Report whether the DOM backend is available."""
    return BeautifulSoup is not None


def clean_soup(html: str) -> Any:
    """Return a soup stripped of script, style, chrome and site navigation."""
    if BeautifulSoup is None:
        return None
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(string=lambda value: isinstance(value, Comment)):
        node.extract()
    for tag in soup.find_all(tuple(SKIP_TAGS)):
        tag.decompose()
    for tag in soup.find_all(True):
        if _is_chrome(tag):
            tag.decompose()
    root = soup
    for selector in CONTENT_SELECTORS:
        content = soup.select_one(selector)
        if content is not None:
            root = content
            break
    for inline in root.find_all(INLINE_UNWRAP_TAGS):
        inline.unwrap()
    root.smooth()
    return root


def dom_to_text(html: str) -> str:
    """Extract clean visible text from the main content DOM subtree."""
    root = clean_soup(html)
    if root is None:
        return ""
    return _normalize(root.get_text("\n"))


def dom_to_markdown(html: str) -> str:
    """Extract clean Markdown with headings and bullets from a DOM subtree."""
    root = clean_soup(html)
    if root is None:
        return ""
    for heading in root.find_all(re.compile(r"^h[1-6]$")):
        level = int(heading.name[1])
        text = heading.get_text(" ", strip=True)
        if text:
            heading.string = f"{'#' * level} {text}"
    for item in root.find_all("li"):
        text = item.get_text(" ", strip=True)
        if text:
            item.string = f"- {text}"
    for link in root.find_all("a", href=True):
        label = link.get_text(" ", strip=True)
        href = str(link.get("href") or "")
        is_js = href.lower().startswith("javascript:")
        if href and label and label != href and not is_js:
            link.string = f"{label} ({href})"
    return _normalize(root.get_text("\n"))


def html_language(html: str) -> str:
    """Read the declared language from the HTML root or metadata tags."""
    if BeautifulSoup is None:
        match = re.search(r'<html[^>]+lang=["\']([^"\']+)', html, re.I)
        return _language_code(match.group(1) if match else "")
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find("html")
    value = str(root.get("lang") or "") if root is not None else ""
    if not value:
        meta = soup.find("meta", attrs={"http-equiv": "content-language"})
        value = str(meta.get("content") or "") if meta is not None else ""
    return _language_code(value)


def _language_code(value: str) -> str:
    code = value.strip().lower().replace("_", "-")
    return code[:2] if len(code) >= 2 else ""


def _is_chrome(tag: Any) -> bool:
    if getattr(tag, "decomposed", False):
        return False
    identifier = " ".join([
        str(tag.get("id") or ""),
        " ".join(str(part) for part in (tag.get("class") or [])),
    ]).lower()
    return any(marker in identifier for marker in CHROME_TOKENS)


def _normalize(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        if not line or any(marker in line for marker in JUNK_MARKERS):
            continue
        lines.append(line)
    return "\n".join(lines)
