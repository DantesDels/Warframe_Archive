"""Localized candidates table and its toolbar."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...formatting import display_kind, display_percent, display_source_status
from ..simple_table import SimpleTable
from .actions import add_manual, apply_status, preview_children, remove_candidate

HEADERS = ["Emplacement", "Titre", "Type", "Pertinence", "État", "Preuve/score"]
STATUS_ACTIONS = (
    ("Activer", "active"),
    ("Suspendre", "suspended"),
    ("Blacklister", "blacklisted"),
)
TOOL_ACTIONS = (
    ("Prévisualiser enfants", preview_children),
    ("Supprimer", remove_candidate),
    ("Ajout manuel", add_manual),
)


def candidates_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build the candidate list with stable sizing and French labels."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addWidget(
        QLabel("Sources découvertes en attente de validation ou filtrées.")
    )
    table = SimpleTable(HEADERS, stretch_columns=[0], elide_first=True)
    rows, ids = _rows(workspace, universe)
    table.set_rows(rows, ids)
    layout.addLayout(_actions(table, workspace, universe, on_change))
    layout.addWidget(table, 1)
    return widget


def _rows(
    workspace: Any, universe: dict[str, Any]
) -> tuple[list[list[str]], list[str]]:
    candidates = cast(
        list[dict[str, Any]], workspace.candidates_for(str(universe["id"]))
    )
    rows = [
        [
            str(item.get("location", "")),
            str(item.get("title", "")),
            display_kind(str(item.get("kind", ""))),
            display_percent(item.get("score", 0)),
            display_source_status(str(item.get("status", ""))),
            str(item.get("proof", "")),
        ]
        for item in candidates
    ]
    return rows, [str(item.get("id", "")) for item in candidates]


def _actions(
    table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None],
) -> QHBoxLayout:
    bar = QHBoxLayout()
    for label, status in STATUS_ACTIONS:
        button = QPushButton(label)
        button.clicked.connect(
            lambda _checked=False, value=status: apply_status(
                table, workspace, on_change, value
            )
        )
        bar.addWidget(button)
    for label, action in TOOL_ACTIONS:
        button = QPushButton(label)
        button.clicked.connect(
            lambda _checked=False, fn=action: fn(
                table, workspace, universe, on_change
            )
        )
        bar.addWidget(button)
    bar.addStretch(1)
    return bar
