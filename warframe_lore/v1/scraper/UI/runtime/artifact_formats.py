"""Writers for the standard document export formats."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_jsonl(path: Path, docs: list[dict[str, Any]]) -> Path:
    lines = [json.dumps(doc, ensure_ascii=False) for doc in docs]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_csv(path: Path, rows: list[dict[str, Any]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else ["id"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_md(
    path: Path, universe: dict[str, Any], docs: list[dict[str, Any]]
) -> Path:
    lines = [f"# {universe['name']}", ""]
    for doc in docs:
        lines.extend([
            f"## {doc['title']}", "",
            doc.get("excerpt", ""), "",
            f"Source: {doc.get('url', '')}", "",
        ])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_sql(path: Path, docs: list[dict[str, Any]]) -> Path:
    values: list[str] = []
    for doc in docs:
        title = str(doc.get("title", "") or "").replace("'", "''")
        url = str(doc.get("url", "") or "").replace("'", "''")
        doc_id = str(doc.get("id", "")).replace("'", "''")
        values.append(f"('{doc_id}', '{title}', '{url}')")
    sql = "CREATE TABLE IF NOT EXISTS documents(id TEXT, title TEXT, url TEXT);\n"
    if values:
        sql += (
            "INSERT INTO documents(id,title,url) VALUES\n"
            + ",\n".join(values)
            + ";\n"
        )
    path.write_text(sql, encoding="utf-8")
    return path
