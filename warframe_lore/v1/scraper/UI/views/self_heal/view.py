"""Quarantaine tab: human review & promotion of sandboxed self-heal selectors."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ....self_heal.models import PROPOSAL_STATUS_LABELS
from ....self_heal.quarantine import proposals_for
from ..simple_table import SimpleTable
from .toolbar import build_actions_bar, build_filter_bar
from .worker import SelfHealScanWorker

_HEADERS = [
    "URL / Source", "Sélecteur proposé", "Avant → Après", "Statut", "Sécurité",
]
_WIDTHS = {1: 170, 2: 145, 3: 110, 4: 115}


def self_heal_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build the Quarantaine tab for human validation of self-heal selectors."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    uid = str(universe.get("id", ""))
    rows, ids, by_id = _build_rows(proposals_for(workspace, uid))

    table = SimpleTable(
        _HEADERS, stretch_columns=[0], left_columns={0, 1},
        multi_select=True, column_widths=_WIDTHS,
    )
    table.set_rows(rows, ids)

    detail = QLabel()
    detail.setObjectName("SelfHealDetail")
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    detail.setMinimumWidth(0)
    workers: list[SelfHealScanWorker] = []

    filter_bar, search, count_lbl = build_filter_bar(
        len(rows), lambda txt: (table.set_filter(txt), _sync())
    )
    actions_bar, bulk_btns = build_actions_bar(
        table, workspace, uid, detail, on_change, workers
    )

    def _sync() -> None:
        sel = table.selected_ids()
        vis = table.proxy.rowCount()
        shown = f"{vis}" if vis == len(rows) else f"{vis}/{len(rows)}"
        sel_txt = f"{len(sel)} sélectionnée(s)" if sel else "aucune sélection"
        count_lbl.setText(f"{shown} propositions · {sel_txt}")
        for btn in bulk_btns:
            btn.setEnabled(bool(sel))
        detail.setText(_detail_text(sel, by_id))

    sel_model = table.selectionModel()
    if sel_model is not None:
        sel_model.selectionChanged.connect(lambda *_a: _sync())

    layout.addLayout(filter_bar)
    layout.addLayout(actions_bar)
    layout.addWidget(table, 1)
    layout.addWidget(detail)
    _sync()
    widget._self_heal_workers = workers  # type: ignore[attr-defined]
    return widget


def _build_rows(
    items: list[dict[str, Any]],
) -> tuple[list[list[str]], list[str], dict[str, dict[str, Any]]]:
    rows, ids, by_id = [], [], {}
    for p in items:
        pid = str(p.get("id", ""))
        st = PROPOSAL_STATUS_LABELS.get(str(p.get("status", "")), "En quarantaine")
        alerts = list(p.get("injection_alerts") or [])
        sec = f"Alerte ({len(alerts)})" if alerts else "Sain (sandbox)"
        delta = f"{p.get('before_chars', 0)} → {p.get('after_chars', 0)} car."
        rows.append([
            str(p.get("url") or p.get("source_id") or ""),
            str(p.get("proposed_selector", "")),
            delta,
            st,
            sec,
        ])
        ids.append(pid)
        by_id[pid] = p
    return rows, ids, by_id


def _detail_text(selected: list[str], by_id: dict[str, dict[str, Any]]) -> str:
    if not selected:
        return (
            "Aucune proposition sélectionnée. Les sélecteurs générés restent en "
            "quarantaine jusqu'à validation humaine explicite (« Promouvoir »)."
        )
    if len(selected) > 1:
        return f"{len(selected)} propositions sélectionnées — action en lot prête."
    p = by_id.get(selected[0]) or {}
    alerts = ", ".join(p.get("injection_alerts") or []) or "aucune"
    b_bp = int(round(float(p.get("before_boilerplate", 0.0)) * 100))
    a_bp = int(round(float(p.get("after_boilerplate", 0.0)) * 100))
    return (
        f"Diagnostic : {p.get('reason', '')} · Boilerplate : {b_bp}% → {a_bp}% · "
        f"Alertes injection neutralisées : {alerts}\n"
        f"Aperçu : {p.get('sample_preview', '')}"
    )
