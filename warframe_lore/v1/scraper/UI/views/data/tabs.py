"""Data tab showing scraped/exported files with safe reset to a clean slate."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QItemSelection, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .cleanup import clear_universe_data, export_dir_for
from .tree import add_dir, data_roots, readable_preview


def data_view(
    workspace: Any,
    universe: dict[str, Any],
    on_change: Callable[[], None] | None = None,
) -> QWidget:
    """Build the Data tab for one universe with preview and clear controls."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(6, 6, 6, 6)
    layout.setSpacing(6)
    uid = str(universe["id"])
    roots = data_roots(workspace, uid)

    bar = QHBoxLayout()
    roots_label = QLabel("Dossiers : " + " | ".join(map(str, roots)))
    roots_label.setToolTip("\n".join(map(str, roots)))
    roots_label.setMinimumWidth(0)
    open_btn = QPushButton("Ouvrir le dossier")
    open_btn.setObjectName("DataOpenFolderButton")
    clear_btn = QPushButton("Vider les données")
    clear_btn.setObjectName("DangerButton")
    clear_btn.setToolTip(
        "Supprime les documents collectés, exécutions, exports et cache incrémental "
        "de cet Univers (conserve l'Univers et ses sources configurées)."
    )
    bar.addWidget(roots_label, 1)
    bar.addWidget(open_btn)
    bar.addWidget(clear_btn)
    layout.addLayout(bar)

    splitter = QSplitter(Qt.Orientation.Horizontal)
    tree = QTreeView()
    tree.setHeaderHidden(True)
    tree.setAlternatingRowColors(True)
    model = QStandardItemModel()
    tree.setModel(model)
    preview = QPlainTextEdit()
    preview.setObjectName("DataPreview")
    preview.setReadOnly(True)
    preview.setPlaceholderText("Sélectionnez un fichier pour afficher son contenu.")
    splitter.addWidget(tree)
    splitter.addWidget(preview)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)
    layout.addWidget(splitter, 1)

    def _reload() -> None:
        _populate(model, data_roots(workspace, uid))
        tree.expandAll()
        preview.setPlainText("")

    def _open_folder() -> None:
        target = export_dir_for(workspace, uid)
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target.resolve())))

    def _clear_data() -> None:
        name = str(universe.get("name") or uid)
        reply = QMessageBox.question(
            widget,
            "Vider les données",
            f"Réinitialiser toutes les données collectées pour « {name} » ?\n\n"
            "• Documents collectés, historique d'exécutions et versions supprimés\n"
            "• Fichiers exportés et cache incrémental réinitialisés\n"
            "• L'Univers et vos sources configurées sont conservés.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        clear_universe_data(workspace, uid)
        _reload()
        if on_change is not None:
            on_change()

    open_btn.clicked.connect(_open_folder)
    clear_btn.clicked.connect(_clear_data)
    _reload()
    selection_model = tree.selectionModel()
    if selection_model is not None:
        def _on_selection_changed(
            _selected: QItemSelection, _deselected: QItemSelection
        ) -> None:
            _show_preview(tree, preview)

        selection_model.selectionChanged.connect(_on_selection_changed)
    return widget


def _populate(model: QStandardItemModel, roots: list[Path]) -> None:
    model.clear()
    root_item = model.invisibleRootItem()
    if not any(path.exists() for path in roots):
        empty = QStandardItem("Aucune donnée exportée pour cet univers.")
        empty.setEditable(False)
        root_item.appendRow(empty)
        return
    for path in roots:
        if path.exists():
            add_dir(root_item, path)


def _show_preview(tree: QTreeView, preview: QPlainTextEdit) -> None:
    index = tree.currentIndex()
    if not index.isValid():
        return
    path = Path(str(index.data(int(Qt.ItemDataRole.UserRole)) or ""))
    if bool(index.data(int(Qt.ItemDataRole.UserRole) + 1)) or not path.is_file():
        preview.setPlainText("")
        return
    preview.setPlainText(readable_preview(path))
