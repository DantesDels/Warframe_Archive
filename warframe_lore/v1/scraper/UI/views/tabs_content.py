"""Simple table tabs for documents and runs."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .simple_table import SimpleTable


def documents_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    docs = cast(list[dict[str, Any]], workspace.documents_for(str(universe["id"])))
    rows = [
        [
            str(d.get("title", "")),
            str(d.get("docType", d.get("format", ""))),
            str(d.get("language", "")),
            f"{int(float(d.get('relevance', 0) or 0) * 100)}%",
            "Oui" if d.get("isDuplicate") else "Non",
        ]
        for d in docs
    ]
    table = SimpleTable(["Titre", "Type", "Langue", "Pertinence", "Doublon"])
    table.set_rows(rows)
    layout.addWidget(table)
    return widget


def runs_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    runs = cast(list[dict[str, Any]], workspace.runs_for(str(universe["id"])))
    rows = [
        [
            str(r.get("id", "")),
            str(r.get("startedAt", r.get("date", ""))),
            str(r.get("status", "")),
            str(cast(dict[str, Any], r.get("counts", {}) or {}).get("emitted", r.get("emitted", ""))),
        ]
        for r in runs
    ]
    table = SimpleTable(["Ex?cution", "Date", "Statut", "?mis"], equal_columns=True)
    table.set_rows(rows)
    layout.addWidget(table)
    return widget
