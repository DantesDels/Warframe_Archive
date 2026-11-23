"""Graphify-inspired composite graph tab, fullscreen viewer and HTML launcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...graph.model import build_graph
from .graphics_view import GraphGraphicsView
from .items import GraphNodeItem, full_location
from .scene import build_scene, filter_graph
from .semantic_worker import (
    SemanticExtractionController,
    load_saved_knowledge_graph,
)
from .sidebar import GraphSidebar
from .toolbar import (
    build_graph_toolbar,
    export_and_open_html,
    make_graph_splitter,
    show_fullscreen_graph,
)


class GraphCanvas(QWidget):
    """Full-height Graphify-style canvas with zoom, filters, search and GraphRAG."""

    def __init__(
        self, graph: dict[str, Any], parent: QWidget | None = None, *,
        allow_popout: bool = True, export_dir: Path | None = None,
        knowledge_graph: dict[str, Any] | None = None,
        workspace: Any = None, universe: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._sources_graph, self._knowledge_graph = graph, knowledge_graph
        self._graph, self._export_dir = graph, export_dir
        self._node_items: list[GraphNodeItem] = []
        self.setMinimumHeight(300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        bar, self.mode_combo, extract_btn = build_graph_toolbar(
            allow_popout=allow_popout, can_extract=bool(workspace and universe),
            on_mode_changed=self.set_mode, on_fit=self.fit_graph,
            on_zoom_in=lambda: self.view.zoom_by(1.25),
            on_zoom_out=lambda: self.view.zoom_by(0.8),
            on_open_html=self.open_html_graph, on_extract=self.extract_knowledge,
            on_fullscreen=self.open_fullscreen,
        )
        self._extractor = SemanticExtractionController(
            workspace, universe, export_dir, extract_btn,
            self._on_extract_done, self._on_extract_error,
        )
        layout.addLayout(bar)
        self.view = GraphGraphicsView(self)
        self.sidebar = GraphSidebar(
            graph, on_filter=self._rebuild_scene,
            on_search=self._focus_search, parent=self,
        )
        self.detail = self.sidebar.detail
        layout.addWidget(make_graph_splitter(self.view, self.sidebar), 1)
        self._rebuild_scene(self.sidebar.enabled_kinds())

    def set_mode(self, mode: str) -> None:
        """Switch between 'sources' and 'knowledge' (GraphRAG) graphs."""
        idx = self.mode_combo.findData(mode)
        if idx >= 0 and self.mode_combo.currentIndex() != idx:
            self.mode_combo.setCurrentIndex(idx)
            return
        empty_kg = {"nodes": [], "edges": [], "meta": {"mode": "knowledge"}}
        self._graph = (
            (self._knowledge_graph or empty_kg)
            if mode == "knowledge"
            else self._sources_graph
        )
        self.sidebar.set_graph(self._graph)
        self._rebuild_scene(self.sidebar.enabled_kinds())

    def extract_knowledge(self) -> None:
        """Launch asynchronous semantic extraction for the current universe."""
        self._extractor.start()

    def _on_extract_done(self, graph: dict[str, Any], summary: str) -> None:
        self._knowledge_graph = graph
        self.set_mode("knowledge")
        self.sidebar.detail.setPlainText(f"Extraction terminée : {summary}")

    def _on_extract_error(self, message: str) -> None:
        self.sidebar.detail.setPlainText(f"Erreur d'extraction : {message}")

    def _rebuild_scene(self, kinds: set[str]) -> None:
        self.scene, self._node_items = build_scene(filter_graph(self._graph, kinds))
        self.view.setScene(self.scene)
        for item in self._node_items:
            item.node_clicked.connect(self.show_node)
        self.fit_graph()

    def _focus_search(self, query: str) -> None:
        needle = query.strip().casefold()
        for item in self._node_items:
            hay = f"{item.node.get('label', '')} {full_location(item.node)}".casefold()
            if needle and needle in hay:
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
        show_fullscreen_graph(
            self,
            lambda dlg: GraphCanvas(
                self._graph, dlg, allow_popout=False,
                export_dir=self._export_dir, knowledge_graph=self._knowledge_graph,
            ),
        )

    def open_html_graph(self) -> Path:
        """Export the interactive Graphify-style HTML graph and open it."""
        return export_and_open_html(self._graph, self._export_dir)


def graph_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the full-height Graph tab for one universe."""
    uid = str(universe.get("id", ""))
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    return GraphCanvas(
        build_graph(workspace, universe_id=uid),
        export_dir=base / "exports" / uid,
        knowledge_graph=load_saved_knowledge_graph(workspace, universe),
        workspace=workspace,
        universe=universe,
    )
