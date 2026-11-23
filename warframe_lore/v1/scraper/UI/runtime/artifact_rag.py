"""RAG artifact writers: chunks, vector adapter and parquet export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...use_cases.pipeline.chunking import chunk_text as _chunk
from .artifact_formats import write_json
from .rag_chunks import iter_doc_chunks


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    return _chunk(text, max_chars=max_chars, overlap=overlap)


def chunk_row(
    doc: dict[str, Any], universe: dict[str, Any], chunk: str, index: int,
    *, with_index: bool = False, with_embedding: bool = False,
    section: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "chunk_id": f"{doc.get('id', 'doc')}::{index}",
        "universe_id": universe.get("id"),
        "source_id": doc.get("sourceId"),
        "url": doc.get("url"),
        "version": doc.get("version", 1),
        "trust_score": doc.get("relevance", 1.0),
        "timestamp": doc.get("lastSeenRunId"),
    }
    if with_index:
        row["chunk_index"] = index
    if section:
        row["section"] = section
    row["text"] = chunk
    if with_embedding:
        row["embedding"] = None
    return row


def write_chunks(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path:
    lines: list[str] = []
    for doc in docs:
        for index, (chunk, section) in enumerate(iter_doc_chunks(doc)):
            row = chunk_row(
                doc, universe, chunk, index, with_index=True, section=section
            )
            lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_vector_adapter(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path:
    items = []
    for doc in docs:
        for index, (chunk, section) in enumerate(iter_doc_chunks(doc)):
            if index >= 3:
                break
            items.append(chunk_row(
                doc, universe, chunk, index, with_embedding=True, section=section
            ))
    payload = {
        "adapter": "sqlite-vec/pgvector-compatible",
        "schema": {
            "table": "chunks",
            "columns": [
                "chunk_id", "universe_id", "source_id", "url", "version",
                "trust_score", "timestamp", "text", "embedding",
            ],
        },
        "items": items,
    }
    return write_json(path, payload)


def write_parquet(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path | None:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None
    rows = []
    for doc in docs:
        for index, (chunk, section) in enumerate(iter_doc_chunks(doc)):
            rows.append(chunk_row(doc, universe, chunk, index, section=section))
    try:
        pd.DataFrame(rows).to_parquet(path, index=False)
        return path
    except Exception:
        return None
