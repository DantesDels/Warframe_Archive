"""Lacunes tab: RAG KnowledgeGap active-learning review and targeted discovery."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from ....gaps import GAP_STATUS_LABELS, gaps_for, gaps_jsonl_path
from ..simple_table import SimpleTable
from .toolbar import build_actions_bar, build_filter_bar
from .worker import GapDiscoveryWorker

_HEADERS = [
    "Question / Lacune", "Confiance", "Hits", "Priorité", "État", "Source", "Requêtes",
]
_WIDTHS = {1: 82, 2: 56, 3: 74, 4: 96, 5: 76}


def gaps_view(
    workspace: Any, universe: dict[str, Any], on_change: Callable[[], None]
) -> QWidget:
    """Build the Lacunes tab for human validation of RAG KnowledgeGaps."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    uid = str(universe.get("id", ""))
    rows, ids, by_id = _build_rows(gaps_for(workspace, uid))

    table = SimpleTable(
        _HEADERS, stretch_columns=[0], left_columns={0, 6},
        multi_select=True, column_widths=_WIDTHS, hidden_columns={6},
    )
    table.set_rows(rows, ids)

    filter_bar, search, count_lbl = build_filter_bar(table, len(rows))
    detail = QLabel()
    detail.setObjectName("CandidateDetail")
    detail.setWordWrap(True)
    detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    detail.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    detail.setMinimumWidth(0)
    workers: list[GapDiscoveryWorker] = []
    actions_bar, bulk_btns = build_actions_bar(
        widget, table, workspace, uid, detail, on_change, workers
    )

    def _sync() -> None:
        sel = table.selected_ids()
        vis = table.proxy.rowCount()
        shown = f"{vis}" if vis == len(rows) else f"{vis}/{len(rows)}"
        sel_txt = f"{len(sel)} sélectionnée(s)" if sel else "aucune sélection"
        count_lbl.setText(f"{shown} lacunes · {sel_txt}")
        for btn in bulk_btns:
            btn.setEnabled(bool(sel))
        detail.setText(_detail_text(sel, by_id, gaps_jsonl_path(workspace)))

    search.textChanged.connect(lambda txt: (table.set_filter(txt), _sync()))
    sel_model = table.selectionModel()
    if sel_model is not None:
        sel_model.selectionChanged.connect(lambda *_a: _sync())

    layout.addLayout(filter_bar)
    layout.addLayout(actions_bar)
    layout.addWidget(table, 1)
    layout.addWidget(detail)
    _sync()
    widget._gap_workers = workers  # type: ignore[attr-defined]
    return widget


def _build_rows(
    items: list[dict[str, Any]],
) -> tuple[list[list[str]], list[str], dict[str, dict[str, Any]]]:
    rows, ids, by_id = [], [], {}
    for g in items:
        gid = str(g.get("id", ""))
        conf = int(round(float(g.get("confidence", 0.0) or 0.0) * 100))
        prio = int(round(float(g.get("priority", 0.0) or 0.0) * 100))
        raw_st = str(g.get("status", "open"))
        status = GAP_STATUS_LABELS.get(raw_st, raw_st)
        queries = " | ".join(str(q) for q in (g.get("suggested_queries") or []))
        rows.append([
            str(g.get("question", "")), f"{conf}%", str(int(g.get("hits", 1) or 1)),
            f"{prio}%", status, str(g.get("source", "rag")), queries,
        ])
        ids.append(gid)
        by_id[gid] = g
    return rows, ids, by_id


def _detail_text(
    selected: list[str], by_id: dict[str, dict[str, Any]], path: Any
) -> str:
    if not selected:
        return (
            f"Source d'ingestion RAG : {path}. Sélectionnez une ou plusieurs "
            "lacunes pour lancer une découverte ciblée ou les marquer résolues."
        )
    if len(selected) > 1:
        return f"{len(selected)} lacunes sélectionnées — action en lot prête."
    item = by_id.get(selected[0]) or {}
    queries = ", ".join(str(q) for q in (item.get("suggested_queries") or []))
    return f"Requêtes ciblées : {queries}" if queries else str(item.get("question", ""))
