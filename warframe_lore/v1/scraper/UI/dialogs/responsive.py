"""Responsive sizing and scrollable container helpers for Qt windows and dialogs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...collect.language import SUPPORTED_LANGUAGES
from ..style import apply_theme


def available_screen_size() -> tuple[int, int]:
    """Return the primary screen's available (width, height) with a safe fallback."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return 1280, 760
    rect = screen.availableGeometry()
    return max(640, rect.width()), max(480, rect.height())


def fit_to_screen(
    widget: QWidget,
    *,
    ideal_width: int,
    ideal_height: int,
    width_ratio: float = 0.9,
    height_ratio: float = 0.85,
) -> None:
    """Clamp widget size and maximum bounds to the available screen area."""
    avail_w, avail_h = available_screen_size()
    max_w = max(480, int(avail_w * width_ratio))
    max_h = max(360, int(avail_h * height_ratio))
    widget.setMaximumSize(avail_w, avail_h)
    widget.resize(min(ideal_width, max_w), min(ideal_height, max_h))


def scrollable_dialog_body(dialog: QDialog) -> tuple[QVBoxLayout, QVBoxLayout]:
    """Create (outer_layout, inner_scrollable_layout) with pinned footer support."""
    apply_theme(dialog)
    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(10, 10, 10, 10)
    outer.setSpacing(8)
    scroll = QScrollArea(dialog)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    content = QWidget()
    content.setObjectName("ScrollContent")
    body = QVBoxLayout(content)
    body.setContentsMargins(2, 2, 6, 2)
    body.setSpacing(8)
    scroll.setWidget(content)
    outer.addWidget(scroll, 1)
    return outer, body


def build_language_checks(
    active_codes: set[str], prefix: str
) -> tuple[QGridLayout, dict[str, QCheckBox]]:
    """Build a responsive 2-row grid of allowed-language checkboxes for dialogs."""
    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(4)
    checks: dict[str, QCheckBox] = {}
    for idx, (c, lbl) in enumerate(SUPPORTED_LANGUAGES):
        cb = QCheckBox(lbl, objectName=f"{prefix}_{c}", checked=c in active_codes)
        checks[c] = cb
        grid.addWidget(cb, idx // 6, idx % 6)
    return grid, checks
