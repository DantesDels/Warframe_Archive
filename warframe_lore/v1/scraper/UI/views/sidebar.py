"""Universe sidebar with filter, icon actions and universe list."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _icon_button(icon: str, tip: str, slot, size: int = 30) -> QPushButton:
    button = QPushButton(icon)
    button.setObjectName("SidebarIconButton")
    button.setToolTip(tip)
    button.setCursor(Qt.PointingHandCursor)
    button.setFixedSize(size, size)
    button.setIconSize(QSize(16, 16))
    button.clicked.connect(slot)
    return button


class _UniverseItem(QWidget):
    def __init__(self, uid: str, name: str, count: int, sidebar: Sidebar):
        super().__init__()
        self.uid = uid
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 4, 6)
        row.setSpacing(2)
        self.label = QLabel(f"{name}\n({count} sources)")
        self.label.setWordWrap(True)
        self.label.setStyleSheet("background: transparent; color: #1e293b;")
        row.addWidget(self.label, 1)
        self.actions = QWidget()
        arow = QHBoxLayout(self.actions)
        arow.setContentsMargins(0, 0, 0, 0)
        arow.setSpacing(2)
        for icon, tip, sig in (
            ("▶", "Exécuter", sidebar.execute_requested),
            ("↻", "Synchroniser l'Univers", sidebar.sync_requested),
            ("✕", "Supprimer", sidebar.delete_requested),
        ):
            btn = _icon_button(icon, tip, lambda _=False, s=sig, u=uid: s.emit(u), 24)
            btn.setStyleSheet(
                "QPushButton#SidebarIconButton{font-size:12px;padding:0;}"
            )
            arow.addWidget(btn)
        self.actions.setVisible(False)
        row.addWidget(self.actions, 0, Qt.AlignRight | Qt.AlignVCenter)

    def set_selected(self, selected: bool) -> None:
        self.actions.setVisible(selected)
        color = "#ffffff" if selected else "#1e293b"
        self.label.setStyleSheet(f"background: transparent; color: {color};")


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
        self._universes: list[dict] = []
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
            row.addWidget(_icon_button(icon, tip, slot))
        row.addStretch(1)
        return row

    def _create_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(_icon_button("+", "Nouvel Univers", self.create_requested.emit))
        return row

    def set_universes(self, universes: list[dict], workspace) -> None:
        self._universes = universes
        self._workspace = workspace
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.filter_input.text().strip().casefold()
        selected = self.selected_id()
        self.list.clear()
        visible = 0
        for universe in self._universes:
            name = universe["name"]
            if query and query not in name.casefold():
                continue
            uid = universe["id"]
            count = len(self._workspace.sources_for(uid))
            item = QListWidgetItem(self.list)
            item.setData(Qt.UserRole, uid)
            item.setSizeHint(_UniverseItem(uid, name, count, self).sizeHint())
            widget = _UniverseItem(uid, name, count, self)
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
            if item.data(Qt.UserRole) == universe_id:
                self.list.setCurrentItem(item)
                self._sync_item_actions(universe_id)
                return
        self._sync_item_actions(None)

    def selected_id(self) -> str | None:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _emit_selection(self, current, _previous) -> None:
        uid = current.data(Qt.UserRole) if current else None
        self._sync_item_actions(uid)
        self.selection_changed.emit(uid)

    def _sync_item_actions(self, uid: str | None) -> None:
        for index in range(self.list.count()):
            item = self.list.item(index)
            widget = self.list.itemWidget(item)
            if isinstance(widget, _UniverseItem):
                widget.set_selected(item.data(Qt.UserRole) == uid)
