"""Candidates tab with curation actions."""

from __future__ import annotations

from typing import Any, Callable, cast

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


def candidates_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(QLabel("Sources d?couvertes en attente de validation ou filtr?es."))
    table = SimpleTable(["Titre", "Emplacement", "Type", "Pertinence", "?tat"])
    ids: list[str] = []
    rows: list[list[str]] = []
    for candidate in cast(list[dict[str, Any]], workspace.candidates_for(str(universe["id"]))):
        ids.append(str(candidate.get("id", "")))
        rows.append(
            [
                str(candidate.get("title", "")),
                str(candidate.get("location", "")),
                str(candidate.get("kind", "")),
                display_percent(candidate.get("score", 0)),
                str(candidate.get("status", "")),
            ]
        )
    table.set_rows(rows, ids)
    bar = QHBoxLayout()
    for label, status in (
        ("Activer", "active"),
        ("Suspendre", "suspended"),
        ("Blacklister", "blacklisted"),
    ):
        button = QPushButton(label)
        button.clicked.connect(
            lambda _checked=False, s=status: _apply(table, workspace, on_change, s)
        )
        bar.addWidget(button)
    for label, fn in (("Supprimer", _remove), ("Ajout manuel", _add_manual)):
        button = QPushButton(label)
        button.clicked.connect(
            lambda _checked=False, f=fn: f(table, workspace, universe, on_change)
        )
        bar.addWidget(button)
    bar.addStretch(1)
    layout.addLayout(bar)
    layout.addWidget(table, 1)
    return widget


def _apply(
    table: SimpleTable, workspace: Any, on_change: Callable[[], None], status: str
) -> None:
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


def _remove(
    table: SimpleTable,
    workspace: Any,
    _universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    candidate_id = table.selected_id()
    if candidate_id:
        workspace.delete_source(f"src-{candidate_id}")
        workspace.remove_candidate(candidate_id)
        on_change()


def _add_manual(
    _table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None],
) -> None:
    value, ok = QInputDialog.getText(
        None,
        "Ajout manuel",
        "URL ou chemin du document :",
    )
    if not ok or not value.strip():
        return
    allowed, reason = validate_import(value.strip())
    if not allowed:
        QMessageBox.critical(None, "S?curit? ? l'import", reason)
        return
    workspace.add_manual_source(str(universe["id"]), value.strip())
    on_change()
