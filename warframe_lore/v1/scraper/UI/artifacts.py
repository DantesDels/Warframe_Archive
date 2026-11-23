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
        doc_id = str(doc.get('id', '')).replace("'", "''")
        vals.append(f"({chr(39)}{doc_id}{chr(39)}, {chr(39)}{title}{chr(39)}, {chr(39)}{url}{chr(39)})")
    sql = "CREATE TABLE IF NOT EXISTS documents(id TEXT, title TEXT, url TEXT);\n"
    if vals:
        sql += "INSERT INTO documents(id,title,url) VALUES\n" + ",\n".join(vals) + ";\n"
    path.write_text(sql, encoding="utf-8")
    return path


def _manifest(_out_dir: Path, universe: dict[str, Any], docs: list[dict[str, Any]],
               files: list[Path]) -> dict[str, Any]:
    return {
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
