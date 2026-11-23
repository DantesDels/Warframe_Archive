"""Toolbar builder and fullscreen dialog helper for GraphCanvas."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...graph.export import export_graph
from ..dialogs.responsive import fit_to_screen
from ..style import apply_theme


def build_graph_toolbar(
    *,
    allow_popout: bool,
    can_extract: bool,
    on_mode_changed: Callable[[str], None],
    on_fit: Callable[[], None],
    on_zoom_in: Callable[[], None],
    on_zoom_out: Callable[[], None],
    on_open_html: Callable[[], Any],
    on_extract: Callable[[], None],
    on_fullscreen: Callable[[], None],
) -> tuple[QHBoxLayout, QComboBox, QPushButton | None]:
    """Create the GraphCanvas top toolbar with mode switcher and action buttons."""
    bar = QHBoxLayout()
    mode_combo = QComboBox()
    mode_combo.setObjectName("GraphModeCombo")
    mode_combo.addItem("Sources", "sources")
    mode_combo.addItem("Connaissances (GraphRAG)", "knowledge")
    mode_combo.currentIndexChanged.connect(
        lambda _i: on_mode_changed(str(mode_combo.currentData() or "sources"))
    )
    bar.addWidget(mode_combo)

    specs: list[tuple[str, str, Callable[[], Any]]] = [
        ("Ajuster la vue", "GraphFitButton", on_fit),
        ("Zoom +", "", on_zoom_in),
        ("Zoom -", "", on_zoom_out),
        ("Ouvrir HTML (Graphify)", "GraphOpenHtmlButton", on_open_html),
    ]
    if can_extract:
        specs.append(("Extraire connaissances", "GraphExtractButton", on_extract))
    if allow_popout:
        specs.append(("Plein écran", "GraphFullscreenButton", on_fullscreen))

    extract_btn: QPushButton | None = None
    for label, obj_name, handler in specs:
        btn = QPushButton(label)
        if obj_name:
            btn.setObjectName(obj_name)
        btn.clicked.connect(handler)
        if obj_name == "GraphExtractButton":
            extract_btn = btn
        bar.addWidget(btn)
    bar.addStretch(1)
    return bar, mode_combo, extract_btn


def show_fullscreen_graph(
    parent: QWidget, canvas_factory: Callable[[QDialog], QWidget]
) -> None:
    """Display a GraphCanvas inside a full-size themed modal dialog."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Atelier v1 — Graphe (Plein écran)")
    apply_theme(dialog)
    lay = QVBoxLayout(dialog)
    lay.setContentsMargins(6, 6, 6, 6)
    lay.addWidget(canvas_factory(dialog), 1)
    fit_to_screen(
        dialog, ideal_width=1440, ideal_height=860, width_ratio=0.94, height_ratio=0.9
    )
    dialog.exec()


def export_and_open_html(graph: dict[str, Any], export_dir: Path | None) -> Path:
    """Export graph JSON + HTML and launch it in the system browser."""
    out_dir = export_dir or (Path(tempfile.gettempdir()) / "atelier_v1_graph")
    html_path = export_graph(out_dir, graph)[1]
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_path.resolve())))
    return html_path


def make_graph_splitter(left: QWidget, right: QWidget) -> QSplitter:
    """Build the 4:1 horizontal splitter holding the canvas view and sidebar."""
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.addWidget(left)
    splitter.addWidget(right)
    splitter.setStretchFactor(0, 4)
    splitter.setStretchFactor(1, 1)
    return splitter
