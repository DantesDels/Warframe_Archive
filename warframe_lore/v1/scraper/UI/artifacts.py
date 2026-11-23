"""Artifact export orchestration for the execution worker."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .exports.buckets import write_buckets
from .exports.markdown import write_corpora
from .runtime.artifact_formats import (
    write_csv as _write_csv,
)
from .runtime.artifact_formats import (
    write_json as _write_json,
)
from .runtime.artifact_formats import (
    write_jsonl as _write_jsonl,
)
from .runtime.artifact_formats import (
    write_md as _write_md,
)
from .runtime.artifact_formats import (
    write_sql as _write_sql,
)
from .runtime.artifact_rag import (
    chunk_text,
)
from .runtime.artifact_rag import (
    write_chunks as _write_chunks,
)
from .runtime.artifact_rag import (
    write_parquet as _write_parquet,
)
from .runtime.artifact_rag import (
    write_vector_adapter as _write_vector_adapter,
)

__all__ = ["chunk_text", "emit_artifacts"]


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
    reporter = kwargs.get("reporter")
    generated_at = datetime.now(UTC).isoformat()
    skipped = {"content", "content_markdown", "sections"}
    rows = [
        {key: value for key, value in doc.items() if key not in skipped}
        for doc in docs
    ]
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
        if writer is None:
            continue
        path = writer()
        if path:
            files.append(path)
        if reporter is not None:
            reporter.export(fmt.upper())
    files.extend(write_buckets(out_dir, docs, generated_at))
    files.extend(write_corpora(out_dir, universe, docs, generated_at))
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
    graph_rag_cfg = kwargs.get("graph_rag_config")
    graph_rag_on = bool(kwargs.get("graph_rag_enabled")) or (
        isinstance(graph_rag_cfg, dict) and bool(graph_rag_cfg.get("enabled"))
    )
    if graph_rag_on:
        from ..semantic.export import export_graphrag_bundle
        from ..semantic.pipeline import extract_docs_semantics

        bundle = extract_docs_semantics(
            docs, str(universe.get("id", "")), llm_budget=graph_rag_cfg
        )
        files.extend(export_graphrag_bundle(out_dir / "graphrag", universe, bundle))
    manifest = _manifest(out_dir, universe, docs, files)
    _write_json(out_dir / "manifest.json", manifest)
    return manifest


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
                "name": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
