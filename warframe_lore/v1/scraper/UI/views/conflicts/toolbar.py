"""Filter and arbitration action toolbars for the Conflicts tab."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from ....truth.arbitration import resolve_conflict
from ..simple_table import SimpleTable
from .trust_dialog import TrustProfilesDialog
from .worker import TruthAnalysisWorker

_STATUS_FILTERS = (
    ("Tous les statuts", ""),
    ("Ouverts", "Ouvert"),
    ("Résolus", "Résolu"),
    ("Obsolètes", "Obsolète"),
    ("Ignorés", "Ignoré"),
)


def build_filter_bar(
    total: int, on_filter: Callable[[], None]
) -> tuple[QHBoxLayout, QLineEdit, QComboBox, QLabel]:
    """Create search input, status filter combo and counter label."""
    bar = QHBoxLayout()
    search = QLineEdit()
    search.setObjectName("ConflictSearchInput")
    search.setClearButtonEnabled(True)
    search.setPlaceholderText("Filtrer les conflits par sujet, valeur ou source...")
    search.textChanged.connect(lambda _t: on_filter())
    status_combo = QComboBox()
    status_combo.setObjectName("ConflictStatusFilter")
    for label, needle in _STATUS_FILTERS:
        status_combo.addItem(label, needle)
    status_combo.currentIndexChanged.connect(lambda _i: on_filter())
    count_lbl = QLabel(f"{total} conflits")
    count_lbl.setObjectName("MutedHint")
    bar.addWidget(search, 1)
    bar.addWidget(status_combo)
    bar.addWidget(count_lbl)
    return bar, search, status_combo, count_lbl


def build_actions_bar(
    parent: QWidget,
    table: SimpleTable,
    workspace: Any,
    universe: dict[str, Any],
    detail: QLabel,
    on_change: Callable[[], None],
    workers: list[TruthAnalysisWorker],
) -> tuple[QHBoxLayout, list[QPushButton]]:
    """Create analysis, trust-profile and human arbitration action buttons."""
    bar = QHBoxLayout()
    uid = str(universe.get("id", ""))

    analyze_btn = QPushButton("Analyser les conflits")
    analyze_btn.setObjectName("AnalyzeConflictsButton")
    trust_btn = QPushButton("Profils de confiance...")
    trust_btn.setObjectName("TrustProfilesButton")

    def _run_analysis() -> None:
        analyze_btn.setEnabled(False)
        analyze_btn.setText("Analyse...")
        worker = TruthAnalysisWorker(workspace, universe)
        workers.append(worker)
        worker.finished_summary.connect(
            lambda msg: (detail.setText(f"Analyse terminée : {msg}"), on_change())
        )
        worker.failed.connect(
            lambda err: (
                analyze_btn.setEnabled(True),
                analyze_btn.setText("Analyser les conflits"),
                detail.setText(f"Erreur d'analyse : {err}"),
            )
        )
        worker.start()

    def _edit_trust() -> None:
        dlg = TrustProfilesDialog(parent, workspace, uid)
        if dlg.exec():
            on_change()

    analyze_btn.clicked.connect(_run_analysis)
    trust_btn.clicked.connect(_edit_trust)
    bar.addWidget(analyze_btn)
    bar.addWidget(trust_btn)

    def _arbitrate(decision: str) -> None:
        selected = table.selected_ids()
        if not selected:
            return
        with workspace.batch_save():
            for cid in selected:
                resolve_conflict(workspace, uid, cid, decision)
        on_change()

    bulk_btns: list[QPushButton] = []
    specs = (
        ("Garder A", "KeepAButton", "keep_a"),
        ("Garder B", "KeepBButton", "keep_b"),
        ("Marquer obsolète", "MarkObsoleteButton", "obsolete"),
        ("Ignorer", "DismissConflictButton", "dismiss"),
    )
    for label, obj_name, decision in specs:
        btn = QPushButton(label)
        btn.setObjectName(obj_name)
        btn.clicked.connect(lambda _c=False, d=decision: _arbitrate(d))
        bar.addWidget(btn)
        bulk_btns.append(btn)
    bar.addStretch(1)
    return bar, bulk_btns
