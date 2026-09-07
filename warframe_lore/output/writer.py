"""Écriture et fusion incrémentale des megafiles JSON.

Chaque bucket (ex: ``Lore_Quetes``) produit un fichier JSON unique dont le
contenu est fusionné de façon incrémentale à chaque run (une page modifiée
est écrasée, sans re-générer l'historique complet).

La logique assistante vit dans ``fusion`` ; ici ne reste que l'orchestrateur.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .models import MegafileMetadata, OutputEntry
from .fusion import (
    atomic_write_json,
    build_megafile,
    now_iso_utc,
    read_existing_entries,
)

log = logging.getLogger("warframe_lore.output")


class MegafileManager:
    """Lit, fusionne et écrit les megafiles d'un répertoire de sortie."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def merge_and_write(self, filename: str, bucket_title: str,
                        new_entries: list[OutputEntry],
                        metadata_note: str = "",
                        live_titles: set[str] | None = None) -> dict[str, Any]:
        """Fusionne les nouvelles entrées dans le megafile du bucket.

        ``live_titles`` : ensemble des titres actuellement résolus pour ce
        bucket.  S'il est fourni, les pages du megafile qui n'y figurent pas
        (disparues des catégories du wiki) sont retirées, pour éviter de
        garder indéfiniment des entrées obsolètes au côté des fraîches.
        """
        megafile_path = self.output_dir / filename
        existing_entries = read_existing_entries(megafile_path)

        if live_titles is not None:
            vanished = [t for t in existing_entries if t not in live_titles]
            if vanished:
                log.info("%s : %d page(s) disparue(s) retirée(s) du megafile",
                         megafile_path.name, len(vanished))
            for title in vanished:
                existing_entries.pop(title, None)

        for entry in new_entries:
            if entry.page_title:
                existing_entries[entry.page_title] = entry.to_json_dict()

        ordered_entries = sorted(
            existing_entries.values(),
            key=lambda entry: entry.get("page_title", ""),
        )

        metadata = MegafileMetadata(
            bucket_title=bucket_title,
            generated_at=now_iso_utc(),
            total_pages=len(ordered_entries),
            source_api="https://wiki.warframe.com/api.php",
            note=metadata_note,
        )
        megafile = build_megafile(metadata, ordered_entries)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(megafile_path, megafile)
        log.info("Écrit %s (%d pages)", megafile_path.name, len(ordered_entries))
        return megafile