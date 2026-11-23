"""Prompt-injection sanitizer and strict CSS selector evaluation sandbox."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

from .detector import compute_boilerplate_ratio

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore_instructions", re.compile(
        r"(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|above|prior)\s+instructions",
        re.IGNORECASE,
    )),
    ("role_override", re.compile(
        r"\b(?:system\s*prompt|you\s+are\s+now|act\s+as\s+system|new\s+instructions)\b",
        re.IGNORECASE,
    )),
    ("script_protocol", re.compile(
        r"(?:javascript:|vbscript:|on(?:error|load|click)\s*=|<\s*script)",
        re.IGNORECASE,
    )),
)
_SAFE_SELECTOR_RE = re.compile(r"^[a-zA-Z0-9_\-#.\s>+\[\]=~\"':,*-]{1,120}$")
_BLOCKED_SELECTOR_TOKENS = (
    "javascript:", "url(", "expression(", "@import", "script",
    "style", "iframe", "object", "embed", "eval(",
)


def sanitize_html_for_llm(
    raw_html: str, *, max_chars: int = 3500
) -> tuple[str, list[str]]:
    """Strip active tags, neutralize prompt injections & build a DOM skeleton."""
    alerts: list[str] = []
    scrubbed = raw_html
    for label, pattern in _INJECTION_PATTERNS:
        if pattern.search(scrubbed):
            alerts.append(label)
            scrubbed = pattern.sub("[REDACTED_INJECTION]", scrubbed)

    soup = BeautifulSoup(scrubbed, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for node in soup.find_all(string=True):
        txt = " ".join(str(node).split())
        if len(txt) > 120:
            node.replace_with(txt[:117] + "...")
    skeleton = str(soup)[:max_chars]
    wrapped = f"<<<UNTRUSTED_HTML>>>\n{skeleton}\n<<<END_UNTRUSTED_HTML>>>"
    return wrapped, alerts


def validate_css_selector(selector: str) -> bool:
    """Verify a proposed CSS selector against strict syntax and safety rules."""
    clean = selector.strip()
    if not clean or len(clean) > 120:
        return False
    if not _SAFE_SELECTOR_RE.match(clean):
        return False
    low = clean.casefold()
    if any(bad in low for bad in _BLOCKED_SELECTOR_TOKENS):
        return False
    return True


def evaluate_selector_in_sandbox(
    raw_html: str, selector: str, current_text: str
) -> tuple[bool, str, float, float]:
    """Run selector in-memory on raw HTML and verify measurable quality gain."""
    if not validate_css_selector(selector):
        return False, "", 1.0, 1.0
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    try:
        matched = soup.select(selector)
    except Exception:  # noqa: BLE001
        return False, "", 1.0, 1.0
    if not matched:
        return False, "", 1.0, 1.0

    chunks = [el.get_text("\n", strip=True) for el in matched]
    after_text = "\n\n".join(c for c in chunks if c).strip()
    before_bp = compute_boilerplate_ratio(current_text)
    after_bp = compute_boilerplate_ratio(after_text)
    before_len = len(current_text.strip())
    after_len = len(after_text)

    if after_len < 50:
        return False, after_text, before_bp, after_bp
    grew = after_len >= max(80, int(before_len * 1.4)) and after_bp <= before_bp + 0.05
    min_clean = max(50, int(before_len * 0.4))
    cleaner = (before_bp - after_bp) >= 0.15 and after_len >= min_clean
    return (grew or cleaner), after_text, before_bp, after_bp


def extract_with_selector(raw_html: str, selector: str) -> str:
    """Safely extract text using a human-promoted CSS selector, or empty string."""
    if not validate_css_selector(selector):
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    parts = [el.get_text("\n", strip=True) for el in soup.select(selector)]
    return "\n\n".join(p for p in parts if p).strip()
