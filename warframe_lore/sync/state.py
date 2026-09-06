"""État de synchronisation incrémental (mode delta).

Stocke, par bucket, le mapping ``titre de page -> {pageid, touched}``.
Au run suivant, seules les pages dont le ``touched`` a changé (ou les
nouvelles) sont re-téléchargées et re-parsées.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("warframe_lore.sync")


def _default_state_file() -> dict[str, Any]:
    """État initial : version + aucune donnée de bucket."""
    return {"version": 1, "buckets": {}}


class SyncState:
    """Charge, met à jour et persist l'état delta sur disque."""

    def __init__(self, state_file_path: Path) -> None:
        self.state_file_path = Path(state_file_path)
        self.data = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Lit l'état disque (repart à zéro si corrompu)."""
        if self.state_file_path.exists():
            try:
                return json.loads(
                    self.state_file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Fichier d'état corrompu %s; repart à zéro : %s",
                            self.state_file_path, exc)
        return _default_state_file()

    def save(self) -> None:
        """Persist l'état de façon atomique."""
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.state_file_path.with_suffix(
            self.state_file_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8")
        temporary_path.replace(self.state_file_path)

    # ------------------------------------------------------------- API
    def tracked_pages_for_bucket(self, bucket_id: str) -> dict[str, dict[str, str]]:
        """Retourne ``{titre: {pageid, touched}}`` du bucket (vide si absent)."""
        return self.data.setdefault("buckets", {}).setdefault(bucket_id, {})

    def has_been_modified(self, bucket_id: str, title: str,
                          touched: str | None) -> bool:
        """Vrai si la page doit être re-téléchargée (nouvelle ou modifiée).

        Si ``touched`` est absent, on ne peut rien comparer -> pas de fetch.
        """
        if touched is None:
            return False
        known_page = self.tracked_pages_for_bucket(bucket_id).get(title)
        return known_page is None or known_page.get("touched") != touched

    def ensure_tracked(self, bucket_id: str, title: str, pageid: int,
                       touched: str | None) -> None:
        """Marque une page comme synchronisée (met à jour le touched)."""
        tracked_pages = self.tracked_pages_for_bucket(bucket_id)
        tracked_pages[title] = {"pageid": pageid, "touched": touched or ""}
        self.data["buckets"][bucket_id] = tracked_pages

    def purge_vanished_pages(self, bucket_id: str,
                             live_page_titles: set[str]) -> None:
        """Retire de l'état les pages disparues de la catégorie résolue."""
        tracked_pages = self.tracked_pages_for_bucket(bucket_id)
        pages_to_remove = [title for title in tracked_pages
                           if title not in live_page_titles]
        for title in pages_to_remove:
            del tracked_pages[title]
            log.info("Bucket '%s' : page disparue retirée '%s'",
                     bucket_id, title)

    def summary(self) -> dict[str, int]:
        """Compte de pages suivies par bucket (pour logs/rapports)."""
        return {
            bucket_id: len(pages)
            for bucket_id, pages in self.data.get("buckets", {}).items()
        }