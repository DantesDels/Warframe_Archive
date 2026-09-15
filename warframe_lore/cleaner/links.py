"""MediaWiki links -> readable text (piped targets, namespaces, sections)."""

from __future__ import annotations

import re

_INTERNAL_LINK_PIPED = re.compile(r"\[\[([^\[\]|]*)\|([^\[\]]*)\]\]")
_INTERNAL_LINK_PLAIN = re.compile(r"\[\[([^\[\]]*)\]\]")
_EXTERNAL_LINK_LABELED = re.compile(r"\[(https?://[^\s\[\]]+)\s+([^\]]+)\]")
_EXTERNAL_LINK_RAW = re.compile(r"\[(https?://[^\s\[\]]+)\]")


def normalise_links(wikitext: str) -> str:
    """Converts links to readable text: [[Target|Label]] -> Label."""
    text = wikitext
    text = _INTERNAL_LINK_PIPED.sub(_replace_piped_link, text)
    text = _INTERNAL_LINK_PLAIN.sub(_replace_plain_link, text)
    text = _EXTERNAL_LINK_LABELED.sub(r"\2", text)
    text = _EXTERNAL_LINK_RAW.sub(r"\1", text)
    return text


def _replace_piped_link(match: re.Match) -> str:
    target, label = match.group(1), match.group(2)
    return label.strip() if label.strip() else _readable_target(target)


def _replace_plain_link(match: re.Match) -> str:
    return _readable_target(match.group(1))


def _readable_target(raw_target: str) -> str:
    """``[[Target]]`` -> readable text (strips section and namespace prefix)."""
    target = raw_target.split("#", 1)[0]
    if ":" in target and not target.lower().startswith("mediawiki"):
        target = target.split(":", 1)[1]
    return target.strip()


__all__ = ["normalise_links"]
