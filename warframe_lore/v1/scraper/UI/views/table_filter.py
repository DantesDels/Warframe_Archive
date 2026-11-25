"""Reusable table filter bar, sort keys and column-sizing helpers."""

from __future__ import annotations

import re
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QLabel, QLineEdit, QTableView

SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 2
_NUM_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*%?\s*$")


def sort_key(text: str) -> float | str:
    """Return a numeric sort value for numbers/percentages, else casefolded text."""
    stripped = text.strip()
    if stripped and (stripped[0].isdigit() or stripped[0] == "-"):
        match = _NUM_RE.match(stripped)
        if match:
            return float(match.group(1))
    return text.casefold()


def configure_header(
    header: QHeaderView,
    count: int,
    *,
    equal_columns: bool,
    stretch_columns: list[int] | None,
) -> None:
    """Apply interactive resizing and optional stretched primary column(s)."""
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    if equal_columns:
        header.setStretchLastSection(True)
        return
    targets = stretch_columns if stretch_columns else [0]
    for column in targets:
        if 0 <= column < count:
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)


def apply_column_sizing(
    table: QTableView,
    count: int,
    *,
    column_widths: dict[int, int],
    hidden_columns: set[int],
    elide_first: bool,
) -> None:
    """Apply explicit widths, hidden columns and clamped auto-widths."""
    header = table.horizontalHeader()
    model = table.model()
    row_count = model.rowCount() if model is not None else 0
    for col in range(count):
        if col in hidden_columns:
            table.setColumnHidden(col, True)
            continue
        if col in column_widths:
            table.setColumnWidth(col, column_widths[col])
        elif header.sectionResizeMode(col) != QHeaderView.ResizeMode.Stretch:
            if row_count <= 80:
                table.resizeColumnToContents(col)
                w = max(76, min(260, table.columnWidth(col) + 16))
                table.setColumnWidth(col, w)
            else:
                table.setColumnWidth(col, 120)
    if elide_first:
        table.horizontalScrollBar().setValue(0)


def build_filter_bar(
    placeholder: str,
    total: int,
    on_filter: Callable[[str], int],
    *,
    unit: str = "éléments",
) -> tuple[QHBoxLayout, QLineEdit, QLabel]:
    """Create a filter QLineEdit with clear button and a live count label."""
    bar = QHBoxLayout()
    bar.setSpacing(8)
    search = QLineEdit()
    search.setObjectName("TableFilterInput")
    search.setClearButtonEnabled(True)
    search.setPlaceholderText(placeholder)
    count_label = QLabel(_count_text(total, total, unit))
    count_label.setObjectName("MutedHint")

    def _on_text(text: str) -> None:
        visible = on_filter(text)
        count_label.setText(_count_text(visible, total, unit))

    search.textChanged.connect(_on_text)
    bar.addWidget(search, 1)
    bar.addWidget(count_label)
    return bar, search, count_label


def _count_text(visible: int, total: int, unit: str) -> str:
    return f"{total} {unit}" if visible == total else f"{visible} / {total} {unit}"
