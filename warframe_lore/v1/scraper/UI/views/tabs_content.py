"""Simple table tabs for documents and runs."""

from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


def _table(headers: list[str], rows: list[list[str]]) -> QTableWidget:
    table = QTableWidget(len(rows), len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectRows)
    table.horizontalHeader().setStretchLastSection(True)
    for row, values in enumerate(rows):
        for col, value in enumerate(values):
            table.setItem(row, col, QTableWidgetItem(str(value)))
    return table


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
    layout.addWidget(_table(["Titre", "Type", "Langue", "Pertinence", "Doublon"], rows))
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
    table = _table(["Exécution", "Date", "Statut", "Émis"], rows)
    layout.addWidget(table)
    return widget
