"""Compact filter, selection and bulk-action toolbars for the candidates tab."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ....collect.language import DEFAULT_ALLOWED_LANGUAGES, is_url_language_allowed
from ..simple_table import SimpleTable
from .actions import add_manual, apply_status, preview_children, remove_candidate

STATUS_FILTERS = (
    ("Tous les états", ""),
    ("Proposés", "Proposé"),
    ("Actifs", "Actif"),
    ("Suspendus", "Suspendu"),
    ("Blacklistés", "Blacklisté"),
)
STATUS_ACTIONS = (
    ("Activer", "active", ""),
    ("Suspendre", "suspended", ""),
    ("Blacklister", "blacklisted", ""),
)


class CandidateFilterProxy(QSortFilterProxyModel):
    """Filter candidates by both free-text query and localized status column."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self._query = ""
        self._status = ""
        self._allowed_languages: tuple[str, ...] = DEFAULT_ALLOWED_LANGUAGES
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

    def set_allowed_languages(self, languages: tuple[str, ...]) -> int:
        """Filter candidates live by allowed URL language codes."""
        self.beginFilterChange()
        self._allowed_languages = languages or DEFAULT_ALLOWED_LANGUAGES
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        return self.rowCount()

    def set_filters(self, query: str, status: str) -> int:
        """Update text + status filter and return visible row count."""
        self.beginFilterChange()
        self._query = query.strip().casefold()
        self._status = status.strip().casefold()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        return self.rowCount()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if model is None:
            return True
        loc = str(model.index(source_row, 0, source_parent).data() or "")
        if not is_url_language_allowed(loc, self._allowed_languages):
            return False
        if self._status:
            state = str(model.index(source_row, 4, source_parent).data() or "")
            if state.casefold() != self._status:
                return False
        if not self._query:
            return True
        for col in range(model.columnCount(source_parent)):
            text = str(model.index(source_row, col, source_parent).data() or "")
            if self._query in text.casefold():
                return True
        return False


def build_filter_and_select_bar(
    table: SimpleTable, proxy: CandidateFilterProxy, on_state: Callable[[], None],
) -> tuple[QHBoxLayout, QLineEdit, QComboBox]:
    """Build search input, status dropdown and Select All / Clear buttons."""
    bar = QHBoxLayout(spacing=6)
    search = QLineEdit(
        objectName="TableFilterInput", clearButtonEnabled=True,
        placeholderText="Filtrer par URL, titre, type ou preuve...",
    )
    status_box = QComboBox(objectName="CandidateStatusFilter")
    for label, value in STATUS_FILTERS:
        status_box.addItem(label, value)
    select_all = QPushButton(
        "Tout sélectionner", objectName="CandidatesSelectAllButton"
    )
    select_all.clicked.connect(table.selectAll)
    clear_sel = QPushButton(
        "Désélectionner", objectName="CandidatesClearSelectionButton"
    )
    clear_sel.clicked.connect(table.clearSelection)

    def _apply() -> None:
        proxy.set_filters(search.text(), str(status_box.currentData() or ""))
        on_state()

    search.textChanged.connect(lambda _t: _apply())
    status_box.currentIndexChanged.connect(lambda _i: _apply())
    for w in (search, status_box, select_all, clear_sel):
        bar.addWidget(w, 1 if w is search else 0)
    return bar, search, status_box


def build_actions_bar(
    table: SimpleTable, workspace: Any, universe: dict[str, Any],
    on_change: Callable[[], None],
) -> tuple[QHBoxLayout, list[QPushButton], QLabel]:
    """Build bulk curation buttons and live selection counter."""
    bar = QHBoxLayout(spacing=6)
    bulk_buttons: list[QPushButton] = []
    for label, status, obj_name in STATUS_ACTIONS:
        btn = QPushButton(label, objectName=obj_name or "")
        btn.clicked.connect(
            lambda _c=False, v=status: apply_status(table, workspace, on_change, v)
        )
        bar.addWidget(btn)
        bulk_buttons.append(btn)
    del_btn = QPushButton("Supprimer", objectName="DangerButton")
    del_btn.clicked.connect(
        lambda _c=False: remove_candidate(table, workspace, universe, on_change)
    )
    bar.addWidget(del_btn)
    bulk_buttons.append(del_btn)
    preview_btn = QPushButton("Prévisualiser enfants")
    preview_btn.clicked.connect(
        lambda _c=False: preview_children(table, workspace, universe, on_change)
    )
    add_btn = QPushButton("+ Ajout manuel")
    add_btn.clicked.connect(
        lambda _c=False: add_manual(table, workspace, universe, on_change)
    )
    count_label = QLabel(objectName="MutedHint")
    for w in (preview_btn, add_btn):
        bar.addWidget(w)
    bar.addStretch(1)
    bar.addWidget(count_label)
    return bar, bulk_buttons, count_label
