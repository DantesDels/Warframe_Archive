"""Toolbar and human promotion actions for the Quarantine (Self-Heal) tab."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ....self_heal.quarantine import promote_proposal, reject_proposal
from ..simple_table import SimpleTable
from .worker import SelfHealScanWorker


def build_filter_bar(
    total: int, on_filter: Callable[[str], None]
) -> tuple[QHBoxLayout, QLineEdit, QLabel]:
    """Create search input and counter for quarantined repair proposals."""
    bar = QHBoxLayout()
    search = QLineEdit()
    search.setObjectName("SelfHealSearchInput")
    search.setClearButtonEnabled(True)
    search.setPlaceholderText("Filtrer par URL, sélecteur, statut ou alerte...")
    search.textChanged.connect(on_filter)
    count_lbl = QLabel(f"{total} propositions")
    count_lbl.setObjectName("MutedHint")
    bar.addWidget(search, 1)
    bar.addWidget(count_lbl)
    return bar, search, count_lbl


def build_actions_bar(
    table: SimpleTable,
    workspace: Any,
    universe_id: str,
    detail: QLabel,
    on_change: Callable[[], None],
    workers: list[SelfHealScanWorker],
) -> tuple[QHBoxLayout, list[QPushButton]]:
    """Create diagnostic scan, human promotion and rejection buttons."""
    bar = QHBoxLayout()
    scan_btn = QPushButton("Diagnostiquer les parseurs")
    scan_btn.setObjectName("SelfHealScanButton")

    def _run_scan() -> None:
        scan_btn.setEnabled(False)
        scan_btn.setText("Diagnostic...")
        worker = SelfHealScanWorker(workspace, universe_id)
        workers.append(worker)
        worker.finished_summary.connect(
            lambda msg: (detail.setText(f"Diagnostic terminé : {msg}"), on_change())
        )
        worker.failed.connect(
            lambda err: (
                scan_btn.setEnabled(True),
                scan_btn.setText("Diagnostiquer les parseurs"),
                detail.setText(f"Erreur diagnostic : {err}"),
            )
        )
        worker.start()

    scan_btn.clicked.connect(_run_scan)
    bar.addWidget(scan_btn)

    promote_btn = QPushButton("Promouvoir le sélecteur")
    promote_btn.setObjectName("PromoteProposalButton")
    reject_btn = QPushButton("Rejeter")
    reject_btn.setObjectName("RejectProposalButton")

    def _apply(action: Callable[[Any, str, str], Any]) -> None:
        selected = table.selected_ids()
        if not selected:
            return
        with workspace.batch_save():
            for pid in selected:
                action(workspace, universe_id, pid)
        on_change()

    promote_btn.clicked.connect(lambda: _apply(promote_proposal))
    reject_btn.clicked.connect(lambda: _apply(reject_proposal))
    bar.addWidget(promote_btn)
    bar.addWidget(reject_btn)
    bar.addStretch(1)
    return bar, [promote_btn, reject_btn]
