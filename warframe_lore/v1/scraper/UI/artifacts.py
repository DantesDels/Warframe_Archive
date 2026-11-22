"""Artifact export helpers for execution worker."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def emit_artifacts(
    out_dir: Path, universe: dict, docs: list[dict], formats: list[str]
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [{k: v for k, v in d.items() if k != "content"} for d in docs]
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
            writer()


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, docs: list[dict]) -> None:
    lines = [json.dumps(d, ensure_ascii=False) for d in docs]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else ["id"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_md(path: Path, universe: dict, docs: list[dict]) -> None:
    lines = [f"# {universe['name']}", ""]
    for doc in docs:
        lines.extend([
            f"## {doc['title']}",
            "",
            doc.get("excerpt", ""),
            "",
            f"Source: {doc.get('url', '')}",
            "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_sql(path: Path, docs: list[dict]) -> None:
    vals = []
    for doc in docs:
        title = doc.get("title", "").replace("'", "''")
        url = doc.get("url", "").replace("'", "''")
        vals.append(f"('{doc.get('id', '')}', '{title}', '{url}')")
    sql = "CREATE TABLE IF NOT EXISTS documents(id TEXT, title TEXT, url TEXT);\n"
    if vals:
        sql += "INSERT INTO documents(id,title,url) VALUES\n" + ",\n".join(vals) + ";\n"
    path.write_text(sql, encoding="utf-8")
