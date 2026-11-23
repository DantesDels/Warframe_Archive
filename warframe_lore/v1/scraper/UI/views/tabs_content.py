"""Filterable, sortable table tabs for documents and runs."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..formatting import coerce_score
from .simple_table import SimpleTable
from .table_filter import build_filter_bar

_RUN_STATUS_LABELS = {
    "completed": "Terminée",
    "done": "Terminée",
    "success": "Terminée",
    "running": "En cours",
    "cancelled": "Annulée",
    "canceled": "Annulée",
    "error": "Erreur",
    "failed": "Erreur",
}


def _percent(value: Any) -> str:
    """Format a relevance score, tolerating legacy or malformed records."""
    return f"{int(coerce_score(value) * 100)}%"


def _format_date(raw: Any) -> str:
    text = str(raw or "").strip()
    return text.replace("T", " ").rstrip("Z")[:19] if text else ""


def _format_status(raw: Any) -> str:
    key = str(raw or "").strip()
    return _RUN_STATUS_LABELS.get(key.casefold(), key)


def documents_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the filterable, sortable Documents tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    docs = cast(list[dict[str, Any]], workspace.documents_for(str(universe["id"])))
    rows = [
        [
            str(d.get("title", "")),
            str(d.get("docType", d.get("format", ""))),
            str(d.get("language", "")),
            _percent(d.get("relevance", 0)),
            "Oui" if d.get("isDuplicate") else "Non",
            str(d.get("url", "")),
        ]
        for d in docs
    ]
    table = SimpleTable(
        ["Titre", "Type", "Langue", "Pertinence", "Doublon", "URL"],
        stretch_columns=[0],
        left_columns={0, 5},
    )
    table.set_rows(rows, [str(d.get("id", "")) for d in docs])
    bar, _, _ = build_filter_bar(
        "Filtrer les documents par titre, type, langue ou URL...",
        len(rows),
        table.set_filter,
        unit="documents",
    )
    layout.addLayout(bar)
    layout.addWidget(table, 1)
    return widget


def runs_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the filterable, sortable Runs tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    runs = cast(list[dict[str, Any]], workspace.runs_for(str(universe["id"])))
    rows = []
    for run in runs:
        counts = run.get("counts")
        if not isinstance(counts, dict):
            counts = {}
        rows.append([
            str(run.get("id", "")),
            _format_date(run.get("startedAt", run.get("date", ""))),
            _format_status(run.get("status", "")),
            str(counts.get("emitted", run.get("emitted", 0))),
        ])
    table = SimpleTable(
        ["Exécution", "Date", "Statut", "Émis"],
        stretch_columns=[0],
        left_columns={0, 1},
    )
    table.set_rows(rows)
    bar, _, _ = build_filter_bar(
        "Filtrer les exécutions par identifiant, date ou statut...",
        len(rows),
        table.set_filter,
        unit="exécutions",
    )
    layout.addLayout(bar)
    layout.addWidget(table, 1)
    return widget
