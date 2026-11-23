"""Artifact export helpers for execution worker."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def emit_artifacts(
    out_dir: Path,
    universe: dict[str, Any],
    docs: list[dict[str, Any]],
    formats: list[str],
    *,
    rag_coupling: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [{k: v for k, v in d.items() if k != "content"} for d in docs]
    files: list[Path] = []
    writers = {
        "json": lambda: _write_json(out_dir / "documents.json", docs),
        "jsonl": lambda: _write_jsonl(out_dir / "documents.jsonl", docs),
        "csv": lambda: _write_csv(out_dir / "documents.csv", rows),
        "markdown": lambda: _write_md(out_dir / "documents.md", universe, docs),
        "sql": lambda: _write_sql(out_dir / "documents.sql", docs),
        "nosql": lambda: _write_json(
            out_dir / "documents.nosql.json",
            {"collection": "documents", "items": docs},
        ),
    }
    for fmt in formats:
        writer = writers.get(fmt)
        if writer:
            path = writer()
            if path:
                files.append(path)
    if rag_coupling:
        files.append(_write_chunks(out_dir / "chunks.jsonl", universe, docs))
        files.append(
            _write_vector_adapter(out_dir / "vectors.sqlite.json", universe, docs)
        )
        parquet = _write_parquet(out_dir / "chunks.parquet", universe, docs)
        if parquet:
            files.append(parquet)
    if bool(kwargs.get("graph_enabled", True)):
        from ..graph.run_graph import write_run_graph

        files.extend(write_run_graph(out_dir, universe, docs))
    manifest = _manifest(out_dir, universe, docs, files)
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_jsonl(path: Path, docs: list[dict[str, Any]]) -> Path:
    lines = [json.dumps(d, ensure_ascii=False) for d in docs]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else ["id"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_md(path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]) -> Path:
    lines = [f"# {universe['name']}", ""]
    for doc in docs:
        lines.extend([
            f"## {doc['title']}", "",
            doc.get("excerpt", ""), "",
            f"Source: {doc.get('url', '')}", "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_sql(path: Path, docs: list[dict[str, Any]]) -> Path:
    vals: list[str] = []
    for doc in docs:
        title = str(doc.get("title", "") or "").replace("'", "''")
        url = str(doc.get("url", "") or "").replace("'", "''")
        doc_id = str(doc.get("id", "")).replace("'", "''")
        vals.append(f"('{doc_id}', '{title}', '{url}')")
    sql = "CREATE TABLE IF NOT EXISTS documents(id TEXT, title TEXT, url TEXT);\n"
    if vals:
        sql += (
            "INSERT INTO documents(id,title,url) VALUES\n"
            + ",\n".join(vals)
            + ";\n"
        )
    path.write_text(sql, encoding="utf-8")
    return path


def _write_chunks(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path:
    lines: list[str] = []
    for doc in docs:
        content = str(doc.get("content", "") or "")
        chunks = chunk_text(content)
        for idx, chunk in enumerate(chunks):
            lines.append(
                json.dumps(
                    {
                        "chunk_id": f"{doc.get('id', 'doc')}::{idx}",
                        "universe_id": universe.get("id"),
                        "source_id": doc.get("sourceId"),
                        "url": doc.get("url"),
                        "version": doc.get("version", 1),
                        "trust_score": doc.get("relevance", 1.0),
                        "timestamp": doc.get("lastSeenRunId"),
                        "chunk_index": idx,
                        "text": chunk,
                    },
                    ensure_ascii=False,
                )
            )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 120) -> list[str]:
    from ..use_cases.pipeline.chunking import chunk_text as _chunk

    return _chunk(text, max_chars=max_chars, overlap=overlap)


def _write_vector_adapter(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path:
    items = []
    for doc in docs:
        for idx, chunk in enumerate(chunk_text(str(doc.get("content", "") or ""))[:3]):
            items.append({
                "chunk_id": f"{doc.get('id', 'doc')}::{idx}",
                "universe_id": universe.get("id"),
                "source_id": doc.get("sourceId"),
                "url": doc.get("url"),
                "version": doc.get("version", 1),
                "trust_score": doc.get("relevance", 1.0),
                "timestamp": doc.get("lastSeenRunId"),
                "text": chunk,
                "embedding": None,
            })
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
    return _write_json(path, payload)


def _write_parquet(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path | None:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None
    rows = []
    for doc in docs:
        for idx, chunk in enumerate(chunk_text(str(doc.get("content", "") or ""))):
            rows.append({
                "chunk_id": f"{doc.get('id', 'doc')}::{idx}",
                "universe_id": universe.get("id"),
                "source_id": doc.get("sourceId"),
                "url": doc.get("url"),
                "version": doc.get("version", 1),
                "trust_score": doc.get("relevance", 1.0),
                "timestamp": doc.get("lastSeenRunId"),
                "text": chunk,
            })
    try:
        pd.DataFrame(rows).to_parquet(path, index=False)
        return path
    except Exception:
        return None


def _manifest(
    _out_dir: Path,
    universe: dict[str, Any],
    docs: list[dict[str, Any]],
    files: list[Path],
) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "universe": {"id": universe.get("id"), "name": universe.get("name")},
        "document_count": len(docs),
        "files": [
            {
                "name": p.name,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
            for p in files
        ],
    }
