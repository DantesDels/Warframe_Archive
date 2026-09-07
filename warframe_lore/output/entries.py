"""Construction des entrées de sortie (factories).

Les dataclasses elles-mêmes (``OutputEntry``, ``MegafileMetadata``) vivent
dans ``output/models/`` ; ce module expose la fabrication conforme au schéma
JSON (champ ``canon_status`` pour segmenter canon vs théories des joueurs).
"""

from __future__ import annotations

from .models import CanonStatus, OutputEntry


def build_output_entry(
    page_title: str,
    category: str,
    touched: str | None,
    content_markdown: str,
    canon_status: CanonStatus,
    pageid: int | None,
    source_wiki_url: str,
) -> OutputEntry:
    """Construit une :class:`OutputEntry` selon le schéma documenté.

    ``source_wiki_url`` est l'URL de base du wiki (ex:
    ``https://wiki.warframe.com/wiki/``).
    """
    date_last_updated = (touched or "")[:10]  # YYYY-MM-DD
    source_page_url = source_wiki_url + page_title.replace(" ", "_")
    return OutputEntry(
        page_title=page_title,
        category=category,
        last_updated=date_last_updated,
        content_markdown=content_markdown,
        canon_status=canon_status,
        source=source_page_url,
        pageid=pageid,
    )