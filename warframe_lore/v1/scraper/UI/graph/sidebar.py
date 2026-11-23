"""Graphify-style right-hand sidebar: search, category filters and inspector."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .items import NODE_COLORS, node_tooltip

KIND_ORDER = (
    ("Universe", "Univers"),
    ("Source", "Sources"),
    ("Document", "Documents"),
    ("Candidate", "Candidats"),
)


class GraphSidebar(QWidget):
    """Search, filter by node kind and inspect selected node metadata."""

    def __init__(
        self,
        graph: dict[str, Any],
        *,
        on_filter: Callable[[set[str]], None],
        on_search: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumWidth(210)
        self.setMaximumWidth(320)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setObjectName("GraphSearchInput")
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Rechercher un nœud...")
        self.search.textChanged.connect(on_search)
        layout.addWidget(self.search)

        counts = _kind_counts(graph)
        box = QGroupBox("Catégories")
        box_lay = QVBoxLayout(box)
        box_lay.setSpacing(4)
        self.checks: dict[str, QCheckBox] = {}
        for kind, label in KIND_ORDER:
            cb = QCheckBox(f"{label} ({counts.get(kind, 0)})")
            cb.setChecked(True)
            color = NODE_COLORS.get(kind, "#64748b")
            cb.setStyleSheet(
                "QCheckBox { color: #0f172a; font-weight: 600; }"
                f"QCheckBox::indicator:checked {{ background: {color};"
                f" border-color: {color}; }}"
            )
            cb.toggled.connect(lambda _c: on_filter(self.enabled_kinds()))
            box_lay.addWidget(cb)
            self.checks[kind] = cb
        layout.addWidget(box)

        info_box = QGroupBox("Détails du nœud")
        info_lay = QVBoxLayout(info_box)
        self.detail = QPlainTextEdit()
        self.detail.setObjectName("GraphNodeDetail")
        self.detail.setReadOnly(True)
        self.detail.setPlainText("Cliquez sur un nœud pour voir ses détails.")
        info_lay.addWidget(self.detail, 1)
        layout.addWidget(info_box, 1)

        nodes_n = len(graph.get("nodes", []))
        edges_n = len(graph.get("edges", []))
        self.stats = QLabel(f"{nodes_n} nœuds · {edges_n} liens")
        self.stats.setObjectName("MutedHint")
        layout.addWidget(self.stats)

    def enabled_kinds(self) -> set[str]:
        """Return the set of currently checked node kinds."""
        return {k for k, cb in self.checks.items() if cb.isChecked()}

    def show_node(self, node: dict[str, Any]) -> None:
        """Render complete node metadata in the inspector box."""
        self.detail.setPlainText(node_tooltip(node))


def _kind_counts(graph: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in graph.get("nodes", []):
        kind = str(node.get("kind", ""))
        counts[kind] = counts.get(kind, 0) + 1
    return counts
