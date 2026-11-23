"""JSONL ingestion and append helpers for RAG KnowledgeGaps (gaps.jsonl)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import KnowledgeGap, clamp_confidence


def gaps_jsonl_path(workspace: Any) -> Path:
    """Return the canonical data/v1/gaps.jsonl path for this workspace."""
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    return base / "gaps.jsonl"


def append_gap_jsonl(path: Path, gap: KnowledgeGap) -> None:
    """Append one KnowledgeGap line to the JSONL log file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "universe_id": gap.universe_id,
        "question": gap.question,
        "confidence": gap.confidence,
        "source": gap.source,
        "notes": gap.notes,
        "timestamp": gap.updated_at,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def ingest_jsonl(
    workspace: Any,
    path: Path | None = None,
    *,
    default_universe_id: str = "",
) -> list[KnowledgeGap]:
    """Ingest unanswered RAG questions from a JSONL file (data/v1/gaps.jsonl)."""
    from .store import record_gap

    target = path or gaps_jsonl_path(workspace)
    if not target.is_file():
        return []
    ingested: list[KnowledgeGap] = []
    for line in target.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        question = str(payload.get("question") or payload.get("query") or "").strip()
        uid = str(
            payload.get("universe_id")
            or payload.get("universeId")
            or payload.get("universe")
            or default_universe_id
        ).strip()
        if not question or not uid:
            continue
        ingested.append(
            record_gap(
                workspace,
                uid,
                question,
                confidence=clamp_confidence(payload.get("confidence", 0.0)),
                source=str(payload.get("source") or "rag"),
                notes=str(payload.get("notes") or ""),
                append_jsonl=False,
            )
        )
    return ingested
