"""HTML sanitization of raw Wikitext: comments, tags, transclusion.

Pure ``str -> str`` functions, tied to HTML/XML markup only.
"""

from __future__ import annotations

import re


def strip_wikitext_comments(wikitext: str) -> str:
    """Removes ``<!-- ... -->`` comments (obsolete edit content)."""
    return re.sub(r"<!--.*?-->", "", wikitext, flags=re.DOTALL)


def convert_html_tags(wikitext: str) -> str:
    """Converts useful HTML tags to Markdown/line breaks, discards the rest.

    HTML tables -> line breaks; lists -> bullets; bold/italic ->
    Markdown; ``<br>`` -> new line; ``<math>``/unknown tags
    -> removal.
    """
    text = wikitext
    text = re.sub(r"</?table[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?tr[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?td[^>]*>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?th[^>]*>", " | ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?ul[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?ol[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?li[^>]*>", "\n* ", text, flags=re.IGNORECASE)
    text = re.sub(r"</?b>|</?strong>", "**", text, flags=re.IGNORECASE)
    text = re.sub(r"</?i>|</?em>", "_", text, flags=re.IGNORECASE)
    text = re.sub(r"</?u>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?br[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?div[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?span[^>]*>", "", text, flags=re.IGNORECASE)
    # Citation references: discard the entire tag (content included).
    text = re.sub(r"<ref[^>/]*/>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # Everything else (math, unknown tags): replace with space.
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def remove_transclusion_tags(wikitext: str) -> str:
    """Removes transclusion tags (<noinclude>, <includeonly>, ...)."""
    text = wikitext
    text = re.sub(r"</?noinclude>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?includeonly>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"</?onlyinclude>", "", text, flags=re.IGNORECASE)
    return text


__all__ = ["strip_wikitext_comments", "convert_html_tags", "remove_transclusion_tags"]
