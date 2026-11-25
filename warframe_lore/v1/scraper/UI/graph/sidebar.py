"""Graphify-style right-hand sidebar: Top-N/degree filters, categories and inspector."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
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
SEMANTIC_KIND_ORDER = (
    ("Person", "Personnages"),
    ("Location", "Lieux"),
    ("Faction", "Factions"),
    ("Concept", "Concepts"),
    ("Timeline", "Chronologie"),
)


class GraphSidebar(QWidget):
    """Search, filter by Top-N/degree/kind and inspect selected node metadata."""

    def __init__(
        self,
        graph: dict[str, Any],
        *,
        on_filter: Callable[[set[str]], None],
        on_search: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_filter = on_filter
        self.setMinimumWidth(220)
        self.setMaximumWidth(330)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 4, 4)
        layout.setSpacing(6)

        self.search = QLineEdit(objectName="GraphSearchInput")
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText("Rechercher un nœud...")
        self.search.textChanged.connect(on_search)
        layout.addWidget(self.search)

        lod_box = QGroupBox("Filtrage & densité")
        lod_lay = QVBoxLayout(lod_box)
        lod_lay.setSpacing(4)
        self.max_nodes_spin = self._add_spin(
            lod_lay, "Nœuds max :", "GraphMaxNodesSpin", 20, 1000, 25, 200
        )
        self.min_degree_spin = self._add_spin(
            lod_lay, "Degré min :", "GraphMinDegreeSpin", 0, 20, 1, 3
        )
        layout.addWidget(lod_box)

        self._cat_box = QGroupBox("Catégories")
        self._cat_lay = QVBoxLayout(self._cat_box)
        self._cat_lay.setSpacing(4)
        self.checks: dict[str, QCheckBox] = {}
        layout.addWidget(self._cat_box)

        info_box = QGroupBox("Détails du nœud")
        info_lay = QVBoxLayout(info_box)
        self.detail = QPlainTextEdit(objectName="GraphNodeDetail")
        self.detail.setReadOnly(True)
        info_lay.addWidget(self.detail, 1)
        layout.addWidget(info_box, 1)

        self.stats = QLabel(objectName="MutedHint")
        layout.addWidget(self.stats)
        self.set_graph(graph)

    def _add_spin(
        self, lay: QVBoxLayout, text: str, name: str, lo: int, hi: int, st: int, v: int
    ) -> QSpinBox:
        row, spin = QHBoxLayout(), QSpinBox(objectName=name)
        spin.setRange(lo, hi)
        spin.setSingleStep(st)
        spin.setValue(v)
        spin.valueChanged.connect(lambda _v: self._on_filter(self.enabled_kinds()))
        row.addWidget(QLabel(text))
        row.addWidget(spin)
        lay.addLayout(row)
        return spin

    def set_graph(self, graph: dict[str, Any]) -> None:
        """Rebuild category checkboxes and stats for a new graph dataset."""
        while self._cat_lay.count():
            item = self._cat_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.checks.clear()
        counts = _kind_counts(graph)
        mode = str((graph.get("meta") or {}).get("mode", ""))
        sem = mode == "knowledge" or any(k in counts for k, _ in SEMANTIC_KIND_ORDER)
        for kind, label in (SEMANTIC_KIND_ORDER if sem else KIND_ORDER):
            cb = QCheckBox(f"{label} ({counts.get(kind, 0)})")
            cb.setChecked(not (sem and kind == "Concept"))
            c = NODE_COLORS.get(kind, "#64748b")
            cb.setStyleSheet(
                "QCheckBox { color: #0f172a; font-weight: 600; }"
                f"QCheckBox::indicator:checked {{ background: {c};"
                f" border-color: {c}; }}"
            )
            cb.toggled.connect(lambda _c: self._on_filter(self.enabled_kinds()))
            self._cat_lay.addWidget(cb)
            self.checks[kind] = cb
        self.detail.setPlainText("Cliquez sur un nœud pour voir ses détails.")
        n_cnt, e_cnt = len(graph.get("nodes", [])), len(graph.get("edges", []))
        self.stats.setText(f"{n_cnt} nœuds · {e_cnt} liens")

    def max_nodes(self) -> int:
        return int(self.max_nodes_spin.value())

    def min_degree(self) -> int:
        return int(self.min_degree_spin.value())

    def update_visible_stats(
        self, shown_n: int, shown_e: int, total_n: int, total_e: int
    ) -> None:
        txt = f"Affichés : {shown_n}/{total_n} nœuds · {shown_e}/{total_e} liens"
        self.stats.setText(txt)

    def enabled_kinds(self) -> set[str]:
        return {k for k, cb in self.checks.items() if cb.isChecked()}

    def show_node(self, node: dict[str, Any]) -> None:
        self.detail.setPlainText(node_tooltip(node))


def _kind_counts(graph: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in graph.get("nodes", []):
        counts[str(node.get("kind", ""))] = counts.get(str(node.get("kind", "")), 0) + 1
    return counts
