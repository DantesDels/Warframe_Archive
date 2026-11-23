"""Compact, multi-selectable candidates curation tab with detail strip."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ...formatting import display_kind, display_percent, display_source_status
from ..simple_table import SimpleTable
from .toolbar import (
    CandidateFilterProxy,
    build_actions_bar,
    build_filter_and_select_bar,
)

HEADERS = ["Emplacement", "Titre", "Type", "Pertinence", "État", "Preuve/score"]
COMPACT_WIDTHS = {1: 155, 2: 86, 3: 78, 4: 88}


def candidates_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build a compact, multi-selectable candidates curation view."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)

    table = SimpleTable(
        HEADERS,
        stretch_columns=[0],
        elide_first=True,
        left_columns={0, 1, 5},
        multi_select=True,
        column_widths=COMPACT_WIDTHS,
        hidden_columns={5},
    )
    proxy = CandidateFilterProxy(table)
    table.use_proxy(proxy)
    rows, ids, by_id = _rows(workspace, universe)
    table.set_rows(rows, ids)

    detail = QLabel()
    detail.setObjectName("CandidateDetail")
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    detail.setMinimumWidth(0)

    actions_bar, bulk_buttons, count_label = build_actions_bar(
        table, workspace, universe, on_change
    )

    def _sync_state() -> None:
        selected = table.selected_ids()
        visible = proxy.rowCount()
        total = len(rows)
        shown = f"{visible}" if visible == total else f"{visible}/{total}"
        sel_txt = f"{len(selected)} sélectionné(s)" if selected else "aucune sélection"
        count_label.setText(f"{shown} candidats · {sel_txt}")
        for btn in bulk_buttons:
            btn.setEnabled(bool(selected))
        detail.setText(_detail_text(selected, by_id))

    filter_bar, _, _ = build_filter_and_select_bar(table, proxy, _sync_state)
    sel_model = table.selectionModel()
    if sel_model is not None:
        sel_model.selectionChanged.connect(lambda *_a: _sync_state())

    layout.addLayout(filter_bar)
    layout.addLayout(actions_bar)
    layout.addWidget(table, 1)
    layout.addWidget(detail)
    _sync_state()
    return widget


def _rows(
    workspace: Any, universe: dict[str, Any]
) -> tuple[list[list[str]], list[str], dict[str, dict[str, Any]]]:
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
    ids = [str(item.get("id", "")) for item in candidates]
    by_id = {str(item.get("id", "")): item for item in candidates}
    return rows, ids, by_id


def _detail_text(selected: list[str], by_id: dict[str, dict[str, Any]]) -> str:
    if not selected:
        return (
            "Astuce : cliquez « Tout sélectionner », Ctrl+clic ou Maj+clic pour "
            "activer, suspendre, blacklister ou supprimer plusieurs candidats."
        )
    if len(selected) > 1:
        return (
            f"{len(selected)} candidats sélectionnés — utilisez Activer, Suspendre, "
            "Blacklister ou Supprimer pour les traiter en lot."
        )
    item = by_id.get(selected[0]) or {}
    loc = str(item.get("location", ""))
    proof = str(item.get("proof", "")).strip()
    return f"URL : {loc}   |   Preuve : {proof}" if proof else f"URL : {loc}"
