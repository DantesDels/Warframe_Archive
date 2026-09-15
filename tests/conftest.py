"""Fixtures pytest partagés pour l'archive.

Le helper ``write_megafile`` sert à produire des megafiles ``out/*.json``
minimalistes pour les tests du store UI ; la fixture ``megafiles`` expose un
répertoire `out/` pré-rempli.  Aucune connexion réseau ni base de données.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def write_megafile(output_dir, bucket_id, pages, metadata=None,
                   mtime=None) -> Path:
    """Écrit un megafile ``<output_dir>/<bucket_id>.json`` (retourne le Path)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    megafile = output_dir / f"{bucket_id}.json"
    megafile.write_text(json.dumps(
        {"metadata": metadata or {}, "pages": pages}, ensure_ascii=False),
        encoding="utf-8")
    if mtime is not None:
        os.utime(megafile, (mtime, mtime + 1))
    return megafile


_ONE_PAGE = [{
    "page_title": "Hildryn",
    "content_markdown": "La Gardienne garde la Terre profonde.",
    "canon_status": "canon",
    "last_updated": "2024-01-02",
}]


@pytest.fixture
def megafiles(tmp_path):
    """Répertoire `out/` temporaire avec deux megafiles (canon/spéculation)."""
    out = tmp_path / "out"
    out.mkdir()
    write_megafile(out, "Premier", [
        {"page_title": "Hildryn",
         "content_markdown": "La Gardienne garde la Terre profonde.",
         "canon_status": "canon", "last_updated": "2024-01-02"},
        {"page_title": "Styanax",
         "content_markdown": "Le lancier spartiate repousse l'ennemi.",
         "canon_status": "speculation", "last_updated": "2024-01-01"},
    ], {"bucket_title": "Études", "generated_at": "2024-01-03"})
    write_megafile(out, "Second", _ONE_PAGE,
                   {"bucket_title": "Reliques", "generated_at": "2024-01-02"})
    return out


@pytest.fixture
def megafile_writer():
    """Accès au helper d'écriture pour les scénarios de reload incrémental."""
    return write_megafile
