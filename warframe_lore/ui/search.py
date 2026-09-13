"""Search — full-text ranking with strict title priority.

Single responsibility: build weighted search/suggestion results
(``_SearchDoc`` pre-folded views) from the loaded corpus.  Title matches
always rank before content matches.
"""

from __future__ import annotations

from typing import NamedTuple

from . import dialogue as dlg


class _SearchDoc(NamedTuple):
    """Vue précalculée d'une page pour la recherche (casefold fait 1 fois)."""

    bucket_id: str
    entry: dict
    title_fold: str
    content_fold: str


class SearchMixin:
    """Recherche plein texte et autocomplétion sur les ``_SearchDoc``."""

    @staticmethod
    def _ranked_hit(e: dict, bucket_id: str, query: str,
                    content: str, match_type: str) -> dict:
        """Construit un résultat de recherche pondéré (titre vs contenu)."""
        return {
            "bucket_id": bucket_id,
            "page_title": e["page_title"],
            "canon_status": e.get("canon_status"),
            "last_updated": e.get("last_updated"),
            "match_type": match_type,
            "snippet": dlg.make_snippet(content, query),
        }

    def search(self, query: str, limit: int = 50, *,
               bucket: str | None = None, canon: str | None = None) -> list[dict]:
        """Recherche plein texte avec pondération stricte des titres.

        Hiérarchie absolue : toute page dont le *titre* contient la requête
        (insensible à la casse, partielle) est rendue en tête de liste, avant
        les simples mentions du terme dans le contenu.  Chaque résultat
        expose ``match_type`` (``title``/``content``).
        """
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for doc in self._search_docs:
            if bucket and doc.bucket_id != bucket:
                continue
            if canon and doc.entry.get("canon_status") != canon:
                continue
            content = doc.entry.get("content_markdown", "")
            if needle in doc.title_fold:
                title_hits.append(self._ranked_hit(
                    doc.entry, doc.bucket_id, query, content, "title"))
            elif needle in doc.content_fold:
                content_hits.append(self._ranked_hit(
                    doc.entry, doc.bucket_id, query, content, "content"))
        title_hits.sort(key=lambda r: (r["bucket_id"],
                                       r["page_title"].casefold()))
        content_hits.sort(key=lambda r: (r["bucket_id"],
                                         r["page_title"].casefold()))
        return (title_hits + content_hits)[:limit]

    def suggest(self, query: str, limit: int = 8) -> list[dict]:
        """Autocomplétion : titres contenant ``query`` (+ contexte bucket)."""
        needle = query.casefold().strip()
        if not needle:
            return []
        title_hits: list[dict] = []
        content_hits: list[dict] = []
        for doc in self._search_docs:
            bucket_id = doc.bucket_id
            bucket_title = self._buckets.get(bucket_id, {}).get("title",
                                                                bucket_id)
            e = doc.entry
            title = e["page_title"]
            title_hit = needle in doc.title_fold
            content_hit = needle in doc.content_fold
            if title_hit:
                title_hits.append({
                    "page_title": title,
                    "bucket_id": bucket_id,
                    "bucket_title": bucket_title,
                    "canon_status": e.get("canon_status"),
                    "match_type": "title",
                    "snippet": "",
                })
            elif content_hit:
                content_hits.append({
                    "page_title": title,
                    "bucket_id": bucket_id,
                    "bucket_title": bucket_title,
                    "canon_status": e.get("canon_status"),
                    "match_type": "content",
                    "snippet": dlg.make_snippet(
                        e.get("content_markdown", ""), query, radius=44),
                })
        title_hits.sort(key=lambda r: (r["bucket_id"],
                                       r["page_title"].casefold()))
        content_hits.sort(key=lambda r: (r["bucket_id"],
                                         r["page_title"].casefold()))
        return (title_hits + content_hits)[:limit]
