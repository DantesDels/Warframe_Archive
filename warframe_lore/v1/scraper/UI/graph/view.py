"""Graphify-inspired composite graph tab, fullscreen viewer and HTML launcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...graph.model import build_graph
from .ego import apply_scene_focus, focus_search_query
from .graphics_view import GraphGraphicsView
from .items import GraphNodeItem
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
    """Full-height Graphify-style canvas with zoom, Top-N, ego-graph and GraphRAG."""

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
        self._selected_id = self._hovered_id = None
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
        self.view.background_clicked.connect(self.clear_focus)
        self.sidebar = GraphSidebar(
            graph, on_filter=self._rebuild_scene,
            on_search=lambda q: focus_search_query(self, q), parent=self,
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
        kg = self._knowledge_graph or empty_kg
        self._graph = kg if mode == "knowledge" else self._sources_graph
        self._selected_id = self._hovered_id = None
        self.sidebar.set_graph(self._graph)
        self._rebuild_scene(self.sidebar.enabled_kinds())

    def extract_knowledge(self) -> None:
        self._extractor.start()

    def _on_extract_done(self, graph: dict[str, Any], summary: str) -> None:
        self._knowledge_graph = graph
        self.set_mode("knowledge")
        self.sidebar.detail.setPlainText(f"Extraction terminée : {summary}")

    def _on_extract_error(self, message: str) -> None:
        self.sidebar.detail.setPlainText(f"Erreur d'extraction : {message}")

    def _sync_focus(self) -> None:
        apply_scene_focus(
            self.scene, self._node_items,
            selected_id=self._selected_id, hovered_id=self._hovered_id,
        )

    def _rebuild_scene(self, kinds: set[str]) -> None:
        sub = filter_graph(
            self._graph, kinds, max_nodes=self.sidebar.max_nodes(),
            min_degree=self.sidebar.min_degree(), focus_id=self._selected_id,
        )
        self.scene, self._node_items = build_scene(sub)
        self.view.setScene(self.scene)
        for item in self._node_items:
            item.node_clicked.connect(self.show_node)
            item.node_hovered.connect(self._on_node_hovered)
        s_n, s_e = len(sub.get("nodes", [])), len(sub.get("edges", []))
        t_n, t_e = len(self._graph.get("nodes", [])), len(self._graph.get("edges", []))
        self.sidebar.update_visible_stats(s_n, s_e, t_n, t_e)
        self._sync_focus()
        self.fit_graph()

    def _on_node_hovered(self, node: dict[str, Any], entered: bool) -> None:
        self._hovered_id = str(node.get("id", "")) if entered else None
        self._sync_focus()

    def clear_focus(self) -> None:
        self._selected_id = None
        self._sync_focus()

    def fit_graph(self) -> None:
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def show_node(self, node: dict[str, Any]) -> None:
        self._selected_id = str(node.get("id", "")) or None
        self._sync_focus()
        self.sidebar.show_node(node)

    def open_fullscreen(self) -> None:
        show_fullscreen_graph(
            self, lambda d: GraphCanvas(
                self._graph, d, allow_popout=False,
                export_dir=self._export_dir, knowledge_graph=self._knowledge_graph,
            ),
        )

    def open_html_graph(self) -> Path:
        return export_and_open_html(self._graph, self._export_dir)


def graph_view(workspace: Any, universe: dict[str, Any]) -> QWidget:
    """Build the full-height Graph tab for one universe."""
    uid = str(universe.get("id", ""))
    ws_path = getattr(workspace, "path", None)
    base = ws_path.parent if isinstance(ws_path, Path) else Path("data/v1")
    return GraphCanvas(
        build_graph(workspace, universe_id=uid), export_dir=base / "exports" / uid,
        knowledge_graph=load_saved_knowledge_graph(workspace, universe),
        workspace=workspace, universe=universe,
    )
