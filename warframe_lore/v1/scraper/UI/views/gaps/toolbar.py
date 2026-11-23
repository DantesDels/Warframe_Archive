"""Toolbar builders for the Lacunes (KnowledgeGap) review tab."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from ..simple_table import SimpleTable
from .actions import (
    add_manual_gap,
    apply_gap_status,
    delete_selected_gaps,
    import_gaps_file,
    launch_gap_discovery,
    toggle_gaps_endpoint,
)
from .worker import GapDiscoveryWorker


def build_filter_bar(
    table: SimpleTable, total: int
) -> tuple[QHBoxLayout, QLineEdit, QLabel]:
    """Create search box, select-all/clear controls and live count label."""
    bar = QHBoxLayout()
    bar.setSpacing(6)
    search = QLineEdit()
    search.setObjectName("TableFilterInput")
    search.setClearButtonEnabled(True)
    search.setPlaceholderText("Filtrer les lacunes par question, état ou requête...")
    sel_all = QPushButton("Tout sélectionner")
    sel_all.setObjectName("GapsSelectAllButton")
    sel_all.clicked.connect(table.selectAll)
    clear_sel = QPushButton("Désélectionner")
    clear_sel.clicked.connect(table.clearSelection)
    count_lbl = QLabel(f"{total} lacunes")
    count_lbl.setObjectName("MutedHint")
    for widget in (search, sel_all, clear_sel, count_lbl):
        bar.addWidget(widget, 1 if widget is search else 0)
    return bar, search, count_lbl


def build_actions_bar(
    parent: QWidget,
    table: SimpleTable,
    workspace: Any,
    uid: str,
    detail: QLabel,
    on_change: Callable[[], None],
    workers: list[GapDiscoveryWorker],
) -> tuple[QHBoxLayout, list[QPushButton]]:
    """Create curation buttons (discover, resolve, ignore, delete, import, add)."""
    bar = QHBoxLayout()
    bar.setSpacing(6)
    discover_btn = QPushButton("Découvrir sources")
    discover_btn.setObjectName("GapsDiscoverButton")
    discover_btn.clicked.connect(
        lambda: launch_gap_discovery(
            parent, table, workspace, uid, detail, on_change, workers
        )
    )
    resolve_btn = QPushButton("Marquer résolue")
    resolve_btn.clicked.connect(
        lambda: apply_gap_status(table, workspace, "resolved", on_change)
    )
    ignore_btn = QPushButton("Ignorer")
    ignore_btn.clicked.connect(
        lambda: apply_gap_status(table, workspace, "ignored", on_change)
    )
    del_btn = QPushButton("Supprimer")
    del_btn.setObjectName("DangerButton")
    del_btn.clicked.connect(lambda: delete_selected_gaps(table, workspace, on_change))
    imp_btn = QPushButton("Importer gaps.jsonl")
    imp_btn.setObjectName("GapsImportButton")
    imp_btn.clicked.connect(lambda: import_gaps_file(parent, workspace, uid, on_change))
    add_btn = QPushButton("+ Ajouter lacune")
    add_btn.setObjectName("GapsAddButton")
    add_btn.clicked.connect(lambda: add_manual_gap(parent, workspace, uid, on_change))
    running = getattr(workspace, "_gaps_server", None)
    ep_btn = QPushButton("Arrêter /gaps" if running else "Démarrer /gaps")
    ep_btn.setObjectName("GapsEndpointButton")
    ep_btn.setToolTip(
        f"Actif sur {running.url}"
        if running
        else "Démarrer le serveur HTTP local POST /gaps (127.0.0.1:8766)"
    )
    ep_btn.clicked.connect(lambda: toggle_gaps_endpoint(workspace, ep_btn, detail))
    bulk = [discover_btn, resolve_btn, ignore_btn, del_btn]
    for btn in (*bulk, imp_btn, add_btn, ep_btn):
        bar.addWidget(btn)
    bar.addStretch(1)
    return bar, bulk
