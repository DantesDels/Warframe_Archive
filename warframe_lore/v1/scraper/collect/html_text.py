"""DOM-aware plain-text fallback that drops non-content elements."""

from __future__ import annotations

from html.parser import HTMLParser

from .dom_clean import CHROME_TOKENS

SKIP_TAGS = frozenset({
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "template", "svg", "iframe", "canvas", "form", "button", "select",
})
BREAK_TAGS = frozenset({
    "article", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5",
    "h6", "hr", "li", "main", "ol", "p", "section", "table", "tr", "ul",
})


class TextExtractor(HTMLParser):
    """Collect text nodes while ignoring script/style/chrome subtrees."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skipped: dict[str, int] = {}
        self._parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Enter skipped elements and mark block boundaries."""
        if tag in SKIP_TAGS or _is_chrome(attrs):
            self._skipped[tag] = self._skipped.get(tag, 0) + 1
        elif not self._skipped and tag in BREAK_TAGS:
            self._parts.append("\n")

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Handle self-closing void elements such as <br/>."""
        if not self._skipped and tag in BREAK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Leave skipped elements and mark block boundaries."""
        if self._skipped.get(tag, 0):
            self._skipped[tag] -= 1
        elif not self._skipped and tag in BREAK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Keep data only outside skipped subtrees."""
        if not self._skipped:
            self._parts.append(data)

    def text(self) -> str:
        """Return normalized, non-empty lines."""
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        return "\n".join(line for line in lines if line)


def _is_chrome(attrs: list[tuple[str, str | None]]) -> bool:
    values = " ".join(str(value or "") for _, value in attrs).lower()
    return any(marker in values for marker in CHROME_TOKENS)


def html_to_text(html: str) -> str:
    """Extract visible text from an HTML document."""
    parser = TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()
