"""Candidates tab with curation actions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..formatting import display_percent
from ..security import validate_import
from .simple_table import SimpleTable


def candidates_view(workspace, universe: dict, on_change) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel(
        "Sources découvertes en attente de validation ou filtrées."
    ))
    table = SimpleTable(["Titre", "Emplacement", "Type", "Pertinence", "État"])
    ids, rows = [], []
    for candidate in workspace.candidates_for(universe["id"]):
        ids.append(candidate["id"])
        rows.append([
            candidate.get("title", ""),
            candidate["location"],
            candidate.get("kind", ""),
            display_percent(candidate.get("score", 0)),
            candidate.get("status", ""),
        ])
    table.set_rows(rows, ids)
    bar = QHBoxLayout()
    for label, status in (
        ("Activer", "active"),
        ("Suspendre", "suspended"),
        ("Blacklister", "blacklisted"),
    ):
        button = QPushButton(label)
        button.clicked.connect(
            lambda _=False, s=status: _apply(table, workspace, on_change, s),
        )
        bar.addWidget(button)
    for label, fn in (("Supprimer", _remove), ("Ajout manuel", _add_manual)):
        button = QPushButton(label)
        button.clicked.connect(
            lambda _=False, f=fn: f(table, workspace, universe, on_change),
        )
        bar.addWidget(button)
    bar.addStretch(1)
    layout.addLayout(bar)
    layout.addWidget(table, 1)
    return widget


def _apply(table, workspace, on_change, status: str) -> None:
    candidate_id = table.selected_id()
    if not candidate_id:
        return
    if status == "active":
        workspace.add_source_from_candidate(candidate_id)
    elif status == "blacklisted":
        workspace.delete_source(f"src-{candidate_id}")
    else:
        workspace.update_candidate(candidate_id, status=status)
    on_change()


def _remove(table, workspace, _universe, on_change) -> None:
    candidate_id = table.selected_id()
    if candidate_id:
        workspace.delete_source(f"src-{candidate_id}")
        workspace.remove_candidate(candidate_id)
        on_change()


def _add_manual(_table, workspace, universe, on_change) -> None:
    value, ok = QInputDialog.getText(
        None, "Ajout manuel", "URL ou chemin du document :",
    )
    if not ok or not value.strip():
        return
    allowed, reason = validate_import(value.strip())
    if not allowed:
        QMessageBox.critical(None, "Sécurité à l'import", reason)
        return
    workspace.add_manual_source(universe["id"], value.strip())
    on_change()
