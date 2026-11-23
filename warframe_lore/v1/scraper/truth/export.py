"""Export claims, inter-source conflicts and temporal history artifacts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import TruthReport


def export_truth_report(
    out_dir: Path,
    universe: dict[str, Any],
    report: TruthReport,
) -> list[Path]:
    """Write claims.jsonl, conflicts.json, temporal_history.json and summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    claims_path = out_dir / "claims.jsonl"
    claims_lines = [
        json.dumps(claim.to_dict(), ensure_ascii=False) for claim in report.claims
    ]
    claims_path.write_text("\n".join(claims_lines), encoding="utf-8")

    conflicts_path = out_dir / "conflicts.json"
    conflicts_path.write_text(
        json.dumps(
            [c.to_dict() for c in report.conflicts], ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )

    history_path = out_dir / "temporal_history.json"
    history_path.write_text(
        json.dumps(
            [h.to_dict() for h in report.history], ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )

    summary_path = out_dir / "truth_summary.json"
    summary = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "universe": {"id": universe.get("id"), "name": universe.get("name")},
        "stats": dict(report.stats),
        "files": [
            "claims.jsonl",
            "conflicts.json",
            "temporal_history.json",
        ],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return [claims_path, conflicts_path, history_path, summary_path]
