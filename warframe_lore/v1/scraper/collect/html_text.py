"""DOM-aware plain-text extraction that drops non-content elements."""

from __future__ import annotations

from html.parser import HTMLParser

SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "template", "svg", "iframe", "canvas"}
)
BREAK_TAGS = frozenset(
    {
        "article",
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "li",
        "main",
        "ol",
        "p",
        "section",
        "table",
        "tr",
        "ul",
    }
)


class TextExtractor(HTMLParser):
    """Collect text nodes while ignoring script/style-like subtrees."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Enter skipped elements and mark block boundaries."""
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BREAK_TAGS and not self._skip_depth:
            self._parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle self-closing void elements such as <br/>."""
        if tag in BREAK_TAGS and not self._skip_depth:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Leave skipped elements and mark block boundaries."""
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BREAK_TAGS and not self._skip_depth:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Keep data only outside skipped subtrees."""
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        """Return normalized, non-empty lines."""
        lines = [" ".join(line.split()) for line in "".join(self._parts).splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_text(html: str) -> str:
    """Extract visible text from an HTML document."""
    parser = TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()
