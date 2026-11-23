"""Universe sidebar with filter, icon actions and universe list."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .sidebar_btn import icon_button
from .sidebar_item import UniverseItem


class Sidebar(QFrame):
    """Left navigation pane for Universe selection and actions."""

    create_requested = Signal()
    rename_requested = Signal()
    settings_requested = Signal()
    execute_requested = Signal(str)
    sync_requested = Signal(str)
    delete_requested = Signal(str)
    sync_all_requested = Signal()
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self._universes: list[dict[str, Any]] = []
        self._workspace: Any = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.title = QLabel("Univers (0)")
        self.title.setStyleSheet("font-weight: 600; color: #1e293b;")
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrer les univers...")
        self.filter_input.setClearButtonEnabled(True)
        self.list = QListWidget()
        self.list.setSpacing(2)
        layout.addWidget(self.title)
        layout.addLayout(self._actions_row())
        layout.addWidget(self.filter_input)
        layout.addWidget(self.list, 1)
        layout.addLayout(self._create_row())
        self.filter_input.textChanged.connect(self._apply_filter)
        self.list.currentItemChanged.connect(self._emit_selection)

    def _actions_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(4)
        for icon, tip, slot in (
            ("✎", "Renommer (F2)", self.rename_requested.emit),
            ("⚙", "Paramètres globaux", self.settings_requested.emit),
            ("↻", "Synchroniser tout", self.sync_all_requested.emit),
        ):
            row.addWidget(icon_button(icon, tip, slot))
        row.addStretch(1)
        return row

    def _create_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(icon_button("+", "Nouvel Univers", self.create_requested.emit))
        return row

    def set_universes(self, universes: list[dict[str, Any]], workspace: Any) -> None:
        self._universes = universes
        self._workspace = workspace
        self._apply_filter()

    def _apply_filter(self, _text: str = "") -> None:
        query = self.filter_input.text().strip().casefold()
        selected = self.selected_id()
        self.list.clear()
        visible = 0
        for universe in self._universes:
            name = str(universe.get("name", ""))
            if query and query not in name.casefold():
                continue
            uid = str(universe.get("id", ""))
            count = (
                len(cast(list[Any], self._workspace.sources_for(uid)))
                if self._workspace is not None
                else 0
            )
            item = QListWidgetItem(self.list)
            item.setData(int(Qt.ItemDataRole.UserRole), uid)
            widget = UniverseItem(uid, name, count, self)
            item.setSizeHint(widget.sizeHint())
            widget.set_selected(uid == selected)
            self.list.setItemWidget(item, widget)
            visible += 1
        self.title.setText(f"Univers ({visible})")
        if selected:
            self.select(selected)

    def select(self, universe_id: str | None) -> None:
        if not universe_id:
            self.list.clearSelection()
            self._sync_item_actions(None)
            return
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item is not None and item.data(int(Qt.ItemDataRole.UserRole)) == universe_id:
                self.list.setCurrentItem(item)
                self._sync_item_actions(universe_id)
                return
        self._sync_item_actions(None)

    def selected_id(self) -> str | None:
        item = self.list.currentItem()
        if item is None:
            return None
        value = item.data(int(Qt.ItemDataRole.UserRole))
        return str(value) if value is not None else None

    def _emit_selection(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        uid = (
            str(current.data(int(Qt.ItemDataRole.UserRole)))
            if current is not None
            else None
        )
        self._sync_item_actions(uid)
        self.selection_changed.emit(uid)

    def _sync_item_actions(self, uid: str | None) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item is None:
                continue
            widget = self.list.itemWidget(item)
            if isinstance(widget, UniverseItem):
                widget.set_selected(item.data(int(Qt.ItemDataRole.UserRole)) == uid)
