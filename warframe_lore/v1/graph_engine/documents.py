"""Read the normalized Scraper v1 export (chunks, titles, manifest).

The engine only consumes the published artifacts of a run directory; it
never imports or modifies the scraper pipeline itself.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..scraper.storage import read_json

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SourceChunk:
    """One normalized chunk with its exact provenance identifiers."""

    chunk_id: str
    document_id: str
    source_id: str
    text: str
    url: str = ""
    section: str = ""
    version: int = 1

    def content_hash(self) -> str:
        """Stable SHA-256 of the chunk text, the incrementality key."""
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            logger.warning("Skipping malformed JSONL line in %s", path)
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def verify_manifest(export_dir: Path) -> dict[str, Any]:
    """Check the export manifest and the chunks file digest when present."""
    manifest = read_json(export_dir / "manifest.json", {})
    if not isinstance(manifest, dict):
        return {}
    chunks_entry = next(
        (f for f in manifest.get("files", []) if f.get("name") == "chunks.jsonl"),
        None,
    )
    chunks_path = export_dir / "chunks.jsonl"
    if chunks_entry and chunks_path.is_file():
        digest = hashlib.sha256(chunks_path.read_bytes()).hexdigest()
        if digest != chunks_entry.get("sha256"):
            logger.warning("chunks.jsonl digest differs from export manifest")
    return manifest


def load_document_titles(export_dir: Path) -> dict[str, str]:
    """Map document ids to titles from documents.jsonl (best effort)."""
    titles: dict[str, str] = {}
    for row in _iter_jsonl(export_dir / "documents.jsonl"):
        doc_id = str(row.get("id") or "")
        if doc_id:
            titles[doc_id] = str(row.get("title") or doc_id)
    return titles


def load_chunks(export_dir: Path) -> list[SourceChunk]:
    """Load every normalized chunk of a Scraper v1 run export."""
    chunks: list[SourceChunk] = []
    for row in _iter_jsonl(export_dir / "chunks.jsonl"):
        chunk_id = str(row.get("chunk_id") or "")
        text = str(row.get("text") or "")
        if not chunk_id or not text.strip():
            continue
        chunks.append(
            SourceChunk(
                chunk_id=chunk_id,
                document_id=chunk_id.split("::")[0],
                source_id=str(row.get("source_id") or ""),
                text=text,
                url=str(row.get("url") or ""),
                section=str(row.get("section") or ""),
                version=int(row.get("version") or 1),
            )
        )
    return chunks
