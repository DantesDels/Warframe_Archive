"""Background QThread worker and controller for semantic GraphRAG extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QPushButton

from ...semantic.export import export_graphrag_bundle, semantic_to_graph_dict
from ...semantic.pipeline import extract_universe_semantics


class SemanticExtractWorker(QThread):
    """Extract entities/relations and export GraphRAG bundle off the UI thread."""

    finished_graph = Signal(object, str)
    failed = Signal(str)

    def __init__(
        self,
        workspace: Any,
        universe: dict[str, Any],
        export_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._universe = universe
        self._export_dir = export_dir

    def run(self) -> None:
        try:
            uid = str(self._universe.get("id", ""))
            name = str(self._universe.get("name", ""))
            bundle = extract_universe_semantics(self._workspace, uid)
            graph = semantic_to_graph_dict(bundle, name)
            summary = (
                f"{len(bundle.entities)} entités · {len(bundle.relations)} relations"
            )
            if self._export_dir is not None:
                export_graphrag_bundle(
                    self._export_dir / "graphrag", self._universe, bundle
                )
            self.finished_graph.emit(graph, summary)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class SemanticExtractionController:
    """Coordinate background extraction and button state for GraphCanvas."""

    def __init__(
        self,
        workspace: Any,
        universe: dict[str, Any] | None,
        export_dir: Path | None,
        button: QPushButton | None,
        on_done: Callable[[dict[str, Any], str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._universe = universe
        self._export_dir = export_dir
        self._button = button
        self._on_done = on_done
        self._on_error = on_error
        self._worker: SemanticExtractWorker | None = None

    def start(self) -> None:
        if self._workspace is None or self._universe is None:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        if self._button is not None:
            self._button.setEnabled(False)
            self._button.setText("Extraction...")
        self._worker = SemanticExtractWorker(
            self._workspace, self._universe, self._export_dir
        )
        self._worker.finished_graph.connect(self._handle_done)
        self._worker.failed.connect(self._handle_error)
        self._worker.start()

    def _reset_button(self) -> None:
        if self._button is not None:
            self._button.setEnabled(True)
            self._button.setText("Extraire connaissances")

    def _handle_done(self, graph: dict[str, Any], summary: str) -> None:
        self._reset_button()
        self._on_done(graph, summary)

    def _handle_error(self, message: str) -> None:
        self._reset_button()
        self._on_error(message)


def load_saved_knowledge_graph(
    workspace: Any, universe: dict[str, Any]
) -> dict[str, Any] | None:
    """Return a previously extracted semantic graph for the universe, if any."""
    uid = str(universe.get("id", ""))
    saved = (workspace.data.get("knowledge_graphs") or {}).get(uid)
    if not isinstance(saved, dict):
        return None
    return semantic_to_graph_dict(saved, str(universe.get("name", "")))
