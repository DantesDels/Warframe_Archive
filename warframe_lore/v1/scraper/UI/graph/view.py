"""Graphify-inspired composite graph tab, fullscreen viewer and HTML launcher."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...graph.export import export_graph
from ...graph.model import build_graph
from ..dialogs.responsive import fit_to_screen
from ..style import apply_theme
from .graphics_view import GraphGraphicsView
from .items import GraphNodeItem, full_location
from .scene import build_scene, filter_graph
from .sidebar import GraphSidebar


class GraphCanvas(QWidget):
    """Full-height Graphify-style canvas with zoom, filters, search and popout."""

    def __init__(
        self,
        graph: dict[str, Any],
        parent: QWidget | None = None,
        *,
        allow_popout: bool = True,
        export_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._graph = graph
        self._export_dir = export_dir
        self._node_items: list[GraphNodeItem] = []
        self.setMinimumHeight(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        layout.addLayout(self._build_toolbar(allow_popout))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.view = GraphGraphicsView(self)
        self.sidebar = GraphSidebar(
            graph,
            on_filter=self._rebuild_scene,
            on_search=self._focus_search,
            parent=self,
        )
        self.detail = self.sidebar.detail
        splitter.addWidget(self.view)
        splitter.addWidget(self.sidebar)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        self._rebuild_scene(self.sidebar.enabled_kinds())

    def _build_toolbar(self, allow_popout: bool) -> QHBoxLayout:
        bar = QHBoxLayout()
        specs: list[tuple[str, str, Any]] = [
            ("Ajuster la vue", "GraphFitButton", self.fit_graph),
            ("Zoom +", "", lambda: self.view.zoom_by(1.25)),
            ("Zoom -", "", lambda: self.view.zoom_by(0.8)),
            ("Ouvrir HTML (Graphify)", "GraphOpenHtmlButton", self.open_html_graph),
        ]
        if allow_popout:
            specs.append(("Plein écran", "GraphFullscreenButton", self.open_fullscreen))
        for label, obj_name, handler in specs:
            btn = QPushButton(label)
            if obj_name:
                btn.setObjectName(obj_name)
            btn.clicked.connect(handler)
            bar.addWidget(btn)
        bar.addStretch(1)
        return bar

    def _rebuild_scene(self, kinds: set[str]) -> None:
        subgraph = filter_graph(self._graph, kinds)
        self.scene, self._node_items = build_scene(subgraph)
        self.view.setScene(self.scene)
        for item in self._node_items:
            item.node_clicked.connect(self.show_node)
        self.fit_graph()

    def _focus_search(self, query: str) -> None:
        needle = query.strip().casefold()
        if not needle:
            return
        for item in self._node_items:
            hay = f"{item.node.get('label', '')} {full_location(item.node)}".casefold()
            if needle in hay:
                self.view.centerOn(item)
                self.show_node(item.node)
                return

    def fit_graph(self) -> None:
        """Fit the visible graph cleanly in the viewport."""
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def show_node(self, node: dict[str, Any]) -> None:
        """Show full node metadata in the right-hand inspector."""
        self.sidebar.show_node(node)

    def open_fullscreen(self) -> None:
        """Open a dedicated large window displaying this graph."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Atelier v1 — Graphe des sources (Plein écran)")
        apply_theme(dialog)
        lay = QVBoxLayout(dialog)
        lay.setContentsMargins(6, 6, 6, 6)
        canvas = GraphCanvas(
            self._graph, dialog, allow_popout=False, export_dir=self._export_dir
        )
        lay.addWidget(canvas, 1)
        fit_to_screen(
            dialog, ideal_width=1440, ideal_height=860,
            width_ratio=0.94, height_ratio=0.9,
        )
        dialog.exec()

    def open_html_graph(self) -> Path:
        """Export the interactive Graphify-style HTML graph and open it."""
        out_dir = self._export_dir or (Path(tempfile.gettempdir()) / "atelier_v1_graph")
        paths = export_graph(out_dir, self._graph)
        html_path = paths[1]
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(html_path.resolve())))
        return html_path


def graph_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the full-height Graph tab for one universe."""
    uid = str(universe.get("id", ""))
    graph = build_graph(workspace, universe_id=uid)
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    return GraphCanvas(graph, export_dir=base / "exports" / uid)
