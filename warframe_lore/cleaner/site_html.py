"""HTML -> Markdown cleaner for the official site pages.

``www.warframe.com`` serves whole documents (SSR): a lot of chrome (nav,
footer, cookie/consent widgets, video embeds) must be discarded before the
page becomes ingestible lore.  The walker drops the blacklisted containers
and converts the surviving landmarks (headings, paragraphs, lists, emphasis)
into plain Markdown — the same ``CleanOutput`` contract as the wikitext
cleaner, so the scraper pipeline is unchanged for the site bucket.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .pipeline import CleanOutput

_SKIP_TAGS = frozenset({
    "nav", "footer", "header", "aside", "script", "style", "svg", "video",
    "iframe", "noscript", "form", "button", "select", "input", "label",
    "template", "canvas", "picture", "figure", "source", "audio", "object",
    "embed", "dialog",
})
# Elements the site sometimes leaves UNCLOSED in the SSR (browsers auto-close
# them at the next content sibling): a plain depth counter would then swallow
# the rest of the page.
_AUTOCLOSE_LOOSE = frozenset({
    "video", "audio", "canvas", "svg", "iframe", "figure", "picture",
    "object", "embed", "dialog",
})
_LOOSE_CHILDREN = frozenset({"source", "track", "param", "wbr"})
_BLOCK_TAGS = frozenset({
    "html", "body", "main", "article", "section", "div", "p", "ul", "ol",
    "table", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6",
})
_HEADINGS = {"h1": "1", "h2": "2", "h3": "3", "h4": "4", "h5": "5", "h6": "6"}
_BOLD = frozenset({"strong", "b"})
_ITALIC = frozenset({"em", "i"})
_BLANK_RUNS = re.compile(r"\n{3,}")


class _MarkdownParser(HTMLParser):
    """Streaming HTML walker emitting a Markdown text buffer."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_stack: list[str] = []

    def _in_skip(self) -> bool:
        return bool(self.skip_stack)

    def _autoclose_leftover(self, tag: str) -> None:
        """Closes unclosed browser containers when real content arrives."""
        if tag in _LOOSE_CHILDREN or not self.skip_stack:
            return
        while self.skip_stack and self.skip_stack[-1] in _AUTOCLOSE_LOOSE:
            self.skip_stack.pop()

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        self._autoclose_leftover(tag)
        if self._in_skip():
            if tag in _SKIP_TAGS and tag not in _LOOSE_CHILDREN:
                self.skip_stack.append(tag)
            return
        if tag in _SKIP_TAGS:
            self.skip_stack.append(tag)
            return
        marker = True
        if tag in _HEADINGS:
            self.parts.append(f"\n{'#' * int(_HEADINGS[tag])} ")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")
        elif tag in _BOLD:
            self.parts.append("**")
        elif tag in _ITALIC:
            self.parts.append("*")
        else:
            marker = False
        if tag in _BLOCK_TAGS and not marker:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.skip_stack:
            if self.skip_stack[-1] == tag:
                self.skip_stack.pop()
            elif tag in self.skip_stack:
                self.skip_stack.remove(tag)
            return
        if tag in _BOLD:
            self.parts.append("**")
        elif tag in _ITALIC:
            self.parts.append("*")
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_skip():
            return
        text = re.sub(r"\s+", " ", data)
        if text.strip():
            self.parts.append(text)


class HtmlCleaner:
    """Extracts article Markdown from a ``warframe.com`` page (raw HTML)."""

    def clean(self, raw_html: str) -> CleanOutput:
        parser = _MarkdownParser()
        parser.feed(raw_html)
        parser.close()
        text = _BLANK_RUNS.sub("\n\n", "\n".join(
            " ".join(line.split()) for line in "".join(parser.parts).splitlines()
            if line.strip()
        )).strip()
        return CleanOutput(
            markdown=text,
            non_canon_detected_in_body=False,
            canon_detected_in_body=False,
        )


__all__ = ["HtmlCleaner"]
