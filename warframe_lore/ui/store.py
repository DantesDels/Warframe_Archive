"""LoreStore — cache en mémoire des megafiles ``out/*.json``.

Façade : compose le chargement incrémental des megafiles
(:mod:`warframe_lore.ui.megafiles`), la recherche plein texte
(:mod:`warframe_lore.ui.search`) et les projections de dialogue KIM
(:mod:`warframe_lore.ui.kim_view`).  Le parsing fin des
répliques/scripts/graphes vit dans ``dialogue*`` ; ici seuls les accès
cohérents au corpus.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from ..kim_dm import KimDM
from .kim_view import KimViewMixin
from .megafiles import MegafilesMixin
from .search import SearchMixin


class LoreStore(MegafilesMixin, SearchMixin, KimViewMixin):
    """Cache en mémoire des megafiles ``out/*.json`` + recherche.

    Le rechargement est **incrémental** : seuls les megafiles dont l'empreinte
    (mtime, taille) a changé sont re-parsés, et les index dérivés (recherche,
    compteurs, récents) ne sont reconstruits qu'à cette occasion. Un verrou
    protège le reload contre les requêtes concurrentes du serveur threadé.
    """

    _RELOAD_INTERVAL = 5.0  # secondes entre deux relectures du disque

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.kim_dm = KimDM(
            self.output_dir / "kim_dm" / "data",
            self.output_dir / "kim_dm" / "dicts",
        )
        self._lock = threading.RLock()
        self._file_state: dict[str, tuple[int, int]] = {}
        self._buckets: dict[str, dict[str, Any]] = {}
        self._pages: dict[str, dict[str, dict]] = {}
        self._search_docs = []
        self._bucket_counts: dict[str, dict[str, int]] = {}
        self._pages_sorted: dict[str, list[dict]] = {}
        self._titles_by_bucket: dict[str, list[str]] = {}
        self._recent: list[dict] = []
        self._last_reload = 0.0
        self.reload()

    # ---------------------------------------------------------------- média
    def page_titles_by_bucket(self) -> dict[str, list[str]]:
        """Titres de toutes les pages de l'archive, groupés par bucket."""
        return self._titles_by_bucket

    # -------------------------------------------------------------- buckets
    def list_buckets(self) -> list[dict]:
        return [
            {
                "id": b["id"],
                "title": b["title"],
                "generated_at": b["generated_at"],
                "total_pages": b["total_pages"],
                "canon": self._count_canon(b["id"]),
                "speculation": self._count_status(b["id"], "speculation"),
            }
            for b in sorted(self._buckets.values(), key=lambda x: x["title"].lower())
        ]

    def _count_canon(self, bucket_id: str) -> int:
        return self._bucket_counts.get(bucket_id, {}).get("canon", 0)

    def _count_status(self, bucket_id: str, status: str) -> int:
        return self._bucket_counts.get(bucket_id, {}).get(status, 0)

    def bucket_exists(self, bucket_id: str) -> bool:
        return bucket_id in self._pages

    def list_pages(self, bucket_id: str) -> list[dict]:
        """Liste légère (sans le contenu) des pages d'un bucket, triée."""
        return self._pages_sorted.get(bucket_id, [])

    def get_page(self, bucket_id: str, title: str) -> dict | None:
        return self._pages.get(bucket_id, {}).get(title)

    # ---------------------------------------------------------------- recent
    def recent(self, limit: int = 20) -> list[dict]:
        """Pages triées par ``last_updated`` décroissant (index précalculé)."""
        return self._recent[:limit]

    # ---------------------------------------------------------------- stats
    def stats(self) -> dict[str, Any]:
        total_pages = sum(len(e) for e in self._pages.values())
        canon = sum(self._count_canon(b) for b in self._pages)
        speculation = sum(self._count_status(b, "speculation")
                          for b in self._pages)
        return {
            "buckets": len(self._buckets),
            "pages": total_pages,
            "canon": canon,
            "speculation": speculation,
            "kim_dialogues": len(self.kim_pages()),
            "last_update": max(
                (b["generated_at"] for b in self._buckets.values()
                 if b["generated_at"]),
                default=None,
            ),
        }
