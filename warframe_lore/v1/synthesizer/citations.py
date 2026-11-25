"""Collapsible raw-source callouts shared by every note level."""

from __future__ import annotations

from collections.abc import Iterable

from ..graph_engine.models import SourceExcerpt

_EXCERPT_LIMIT = 300


def sources_callout(
    source_ids: Iterable[str],
    sources: dict[str, SourceExcerpt],
    title: str,
) -> list[str]:
    """Render unique sources as a foldable Obsidian cite callout."""
    lines = [f"> [!cite]- {title}"]
    unique = list(dict.fromkeys(source_ids))
    if not unique:
        lines.append("> (aucune source)")
        return lines
    for source_id in unique:
        excerpt = sources.get(source_id)
        if excerpt is None:
            lines.append(f"> - `{source_id}`")
            continue
        text = " ".join(excerpt.text.split())[:_EXCERPT_LIMIT]
        label = excerpt.document_title or excerpt.url or source_id
        lines.append(f"> - **{label}** (`{source_id}`) : {text}")
    return lines
