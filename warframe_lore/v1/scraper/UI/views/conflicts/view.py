"""Conflits tab: cross-source contradiction review, trust & temporal history."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ....truth.arbitration import conflicts_for, truth_state_for
from ....truth.models import CONFLICT_STATUS_LABELS
from ....truth.trust import trust_label
from ..simple_table import SimpleTable
from .toolbar import build_actions_bar, build_filter_bar
from .worker import TruthAnalysisWorker

_HEADERS = [
    "Sujet", "Attribut", "Valeur A", "Valeur B", "Statut", "Recommandation",
]
_WIDTHS = {1: 110, 4: 96, 5: 135}
_REC_LABELS = {"keep_a": "Source A", "keep_b": "Source B", "none": "Arbitrage requis"}


def conflicts_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build the Conflits tab for human arbitration & temporal truth review."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    uid = str(universe.get("id", ""))
    state = truth_state_for(workspace, uid)
    rows, ids, by_id = _build_rows(conflicts_for(workspace, uid))

    table = SimpleTable(
        _HEADERS, stretch_columns=[0, 2, 3], left_columns={0, 1, 2, 3},
        multi_select=True, column_widths=_WIDTHS,
    )
    table.set_rows(rows, ids)

    detail = QLabel()
    detail.setObjectName("ConflictDetail")
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    detail.setMinimumWidth(0)
    workers: list[TruthAnalysisWorker] = []

    def _apply_filters() -> None:
        query = search.text().strip()
        status_needle = str(status_combo.currentData() or "")
        combined = f"{query} {status_needle}".strip() if status_needle else query
        table.set_filter(combined)
        _sync()

    filter_bar, search, status_combo, count_lbl = build_filter_bar(
        len(rows), _apply_filters
    )
    actions_bar, bulk_btns = build_actions_bar(
        widget, table, workspace, universe, detail, on_change, workers
    )

    def _sync() -> None:
        sel = table.selected_ids()
        vis = table.proxy.rowCount()
        shown = f"{vis}" if vis == len(rows) else f"{vis}/{len(rows)}"
        sel_txt = f"{len(sel)} sélectionné(s)" if sel else "aucune sélection"
        hist_n = len(state.get("history") or [])
        count_lbl.setText(f"{shown} conflits · {hist_n} évolutions · {sel_txt}")
        for btn in bulk_btns:
            btn.setEnabled(bool(sel))
        detail.setText(_detail_text(sel, by_id, state))

    sel_model = table.selectionModel()
    if sel_model is not None:
        sel_model.selectionChanged.connect(lambda *_a: _sync())

    layout.addLayout(filter_bar)
    layout.addLayout(actions_bar)
    layout.addWidget(table, 1)
    layout.addWidget(detail)
    _sync()
    widget._conflict_workers = workers  # type: ignore[attr-defined]
    return widget


def _build_rows(
    items: list[dict[str, Any]],
) -> tuple[list[list[str]], list[str], dict[str, dict[str, Any]]]:
    rows, ids, by_id = [], [], {}
    for item in items:
        cid = str(item.get("id", ""))
        pa = trust_label(str(item.get("source_a_profile", "third_party")))
        pb = trust_label(str(item.get("source_b_profile", "third_party")))
        st = CONFLICT_STATUS_LABELS.get(str(item.get("status", "open")), "Ouvert")
        rec = _REC_LABELS.get(str(item.get("recommended", "none")), "Arbitrage")
        rows.append([
            str(item.get("subject", "")),
            str(item.get("predicate", "")),
            f"{item.get('value_a', '')} [{pa}]",
            f"{item.get('value_b', '')} [{pb}]",
            st,
            rec,
        ])
        ids.append(cid)
        by_id[cid] = item
    return rows, ids, by_id


def _detail_text(
    selected: list[str], by_id: dict[str, dict[str, Any]], state: dict[str, Any]
) -> str:
    if not selected:
        st = state.get("stats") or {}
        claims_n = int(st.get("claim_count", 0) or 0)
        hist_n = len(state.get("history") or [])
        return (
            f"{claims_n} affirmations analysées · {hist_n} évolution(s). "
            "Cliquez sur « Analyser les conflits » ou sélectionnez un conflit."
        )
    if len(selected) > 1:
        return f"{len(selected)} conflits sélectionnés — arbitrage en lot prêt."
    c = by_id.get(selected[0]) or {}
    pa = trust_label(str(c.get("source_a_profile", "")))
    pb = trust_label(str(c.get("source_b_profile", "")))
    lines = [
        f"Motif : {c.get('reason', '')}",
        f"Preuve A ({pa}) : {c.get('evidence_a', '')}",
        f"Preuve B ({pb}) : {c.get('evidence_b', '')}",
    ]
    if c.get("llm_verdict"):
        lines.append(f"Verdict LLM : {c['llm_verdict']}")
    return "\n".join(lines)
