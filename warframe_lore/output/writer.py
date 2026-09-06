"""Écriture et fusion incrémentale des megafiles JSON.

Chaque bucket (ex: ``Lore_Quetes``) produit un fichier JSON unique dont le
contenu est fusionné de façon incrémentale à chaque run (une page modifiée
est écrasée, sans re-générer l'historique complet).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import MegafileMetadata, OutputEntry

log = logging.getLogger("warframe_lore.output")


def _now_iso_utc() -> str:
    """Horodatage ISO UTC (secondes) pour la métadonnée ``generated_at``."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_existing_entries(megafile_path: Path) -> dict[str, dict]:
    """Lit un megafile et retourne ``{page_title: entry}`` (vide si absent)."""
    if not megafile_path.exists():
        return {}
    try:
        raw_data = json.loads(megafile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Impossible de lire %s (%s); reconstruction à vide",
                    megafile_path, exc)
        return {}
    pages_list = raw_data.get("pages", []) if isinstance(raw_data, dict) else raw_data
    return {entry.get("page_title", ""): entry
            for entry in pages_list if entry.get("page_title")}


class MegafileManager:
    """Lit, fusionne et écrit les megafiles d'un répertoire de sortie."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)

    def merge_and_write(self, filename: str, bucket_title: str,
                        new_entries: list[OutputEntry],
                        metadata_note: str = "") -> dict[str, Any]:
        """Fusionne les nouvelles entrées dans le megafile du bucket.

        Returns:
            Le dict complet du megafile (également écrit sur disque).
        """
        megafile_path = self.output_dir / filename
        existing_entries = _read_existing_entries(megafile_path)

        for entry in new_entries:
            if entry.page_title:
                existing_entries[entry.page_title] = entry.to_json_dict()

        ordered_entries = sorted(
            existing_entries.values(),
            key=lambda entry: entry.get("page_title", ""),
        )

        metadata = MegafileMetadata(
            bucket_title=bucket_title,
            generated_at=_now_iso_utc(),
            total_pages=len(ordered_entries),
            source_api="https://wiki.warframe.com/api.php",
            note=metadata_note,
        )
        megafile = _build_megafile(metadata, ordered_entries)

        self.output_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(megafile_path, megafile)
        log.info("Écrit %s (%d pages)", megafile_path.name, len(ordered_entries))
        return megafile


def _build_megafile(metadata: MegafileMetadata,
                    ordered_entries: list[dict]) -> dict[str, Any]:
    """Assemble le dict conforme au schéma ``{"metadata": ..., "pages": [...]}``."""
    return {
        "metadata": {
            "bucket_title": metadata.bucket_title,
            "generated_at": metadata.generated_at,
            "total_pages": metadata.total_pages,
            "source_api": metadata.source_api,
            "note": metadata.note,
        },
        "pages": ordered_entries,
    }


def _atomic_write_json(megafile_path: Path, payload: dict[str, Any]) -> None:
    """Écrit le JSON de façon atomique (fichier temp + rename)."""
    temporary_path = megafile_path.with_suffix(megafile_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary_path.replace(megafile_path)