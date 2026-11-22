"""Simple table tabs for documents and runs."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from .simple_table import SimpleTable


def documents_view(workspace, universe) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    rows = [
        [
            d["title"],
            d.get("docType", d.get("format", "")),
            d.get("language", ""),
            f"{int(d.get('relevance', 0) * 100)}%",
            "Oui" if d.get("isDuplicate") else "Non",
        ]
        for d in workspace.documents_for(universe["id"])
    ]
    table = SimpleTable(["Titre", "Type", "Langue", "Pertinence", "Doublon"])
    table.set_rows(rows)
    layout.addWidget(table)
    return widget


def runs_view(workspace, universe) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    rows = [
        [
            r["id"],
            r.get("startedAt", r.get("date", "")),
            r.get("status", ""),
            str(r.get("counts", {}).get("emitted", r.get("emitted", ""))),
        ]
        for r in workspace.runs_for(universe["id"])
    ]
    table = SimpleTable(["Exécution", "Date", "Statut", "Émis"], equal_columns=True)
    table.set_rows(rows)
    layout.addWidget(table)
    return widget
