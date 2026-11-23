"""Data tab showing scraped/exported file architecture for a universe."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelection, Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)


def data_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)

    root = _data_root(workspace, str(universe["id"]))
    layout.addWidget(QLabel(f"Dossier de données : {root}"))

    splitter = QSplitter(Qt.Orientation.Horizontal)
    tree = QTreeView()
    tree.setHeaderHidden(True)
    model = QStandardItemModel()
    tree.setModel(model)
    preview = QPlainTextEdit()
    preview.setReadOnly(True)
    preview.setPlaceholderText("Sélectionnez un fichier pour afficher son contenu.")
    splitter.addWidget(tree)
    splitter.addWidget(preview)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)
    layout.addWidget(splitter, 1)

    _populate(model, root)
    tree.expandAll()
    selection_model = tree.selectionModel()
    if selection_model is not None:
        def _on_selection_changed(_selected: QItemSelection,
            _deselected: QItemSelection) -> None:
            _show_preview(tree, preview)

        selection_model.selectionChanged.connect(_on_selection_changed)
    return widget


def _data_root(workspace: Any, universe_id: str) -> Path:
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    return base / "exports" / universe_id


def _populate(model: QStandardItemModel, root: Path) -> None:
    model.clear()
    root_item = model.invisibleRootItem()
    if not root.exists():
        empty = QStandardItem("Aucune donnée exportée pour cet univers.")
        empty.setEditable(False)
        root_item.appendRow(empty)
        return
    _add_dir(root_item, root)


def _add_dir(parent: QStandardItem, path: Path) -> None:
    for child in sorted(path.iterdir(), key=_sort_key):
        label = child.name + ("/" if child.is_dir() else _size_suffix(child))
        item = QStandardItem(label)
        item.setEditable(False)
        item.setData(str(child), int(Qt.ItemDataRole.UserRole))
        item.setData(child.is_dir(), int(Qt.ItemDataRole.UserRole) + 1)
        parent.appendRow(item)
        if child.is_dir():
            _add_dir(item, child)


def _sort_key(path: Path) -> tuple[int, str]:
    return (0 if path.is_dir() else 1, path.name.lower())


def _size_suffix(path: Path) -> str:
    try:
        size = float(path.stat().st_size)
    except OSError:
        return ""
    for unit in ("o", "Ko", "Mo", "Go"):
        if size < 1024 or unit == "Go":
            if unit == "o":
                return f" ({int(size)} {unit})"
            return f" ({size:.0f} {unit})"
        size /= 1024
    return ""


def _show_preview(tree: QTreeView, preview: QPlainTextEdit) -> None:
    index = tree.currentIndex()
    if not index.isValid():
        return
    path = Path(str(index.data(int(Qt.ItemDataRole.UserRole)) or ""))
    if bool(index.data(int(Qt.ItemDataRole.UserRole) + 1)) or not path.is_file():
        preview.setPlainText("")
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        preview.setPlainText(f"Impossible de lire le fichier: {exc}")
        return
    limit = 200_000
    if len(text) > limit:
        text = text[:limit] + "\n\n[... aperçu tronqué ...]"
    preview.setPlainText(text)
