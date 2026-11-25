"""QGraphicsView with wheel zoom, drag-to-pan and fast LOD interaction mode."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsView

from .ego import set_fast_interaction

ZOOM_FACTOR = 1.18


class GraphGraphicsView(QGraphicsView):
    """Zoom with the wheel or toolbar, pan by dragging, and throttle AA in motion."""

    background_clicked = Signal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate
        )
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True
        )
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#0f172a")))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._pan_origin: QPoint | None = None
        self._press_origin: QPoint | None = None
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.setInterval(120)
        self._restore_timer.timeout.connect(self._end_fast_interaction)

    def _begin_fast_interaction(self) -> None:
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        set_fast_interaction(self.scene(), True)
        self._restore_timer.start(120)

    def _end_fast_interaction(self) -> None:
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        set_fast_interaction(self.scene(), False)
        self.viewport().update()

    def zoom_by(self, factor: float) -> None:
        """Apply a zoom multiplier while clamping extreme scale values."""
        current = self.transform().m11()
        if (factor > 1 and current > 6.0) or (factor < 1 and current < 0.1):
            return
        self._begin_fast_interaction()
        self.scale(factor, factor)

    def wheelEvent(self, event: Any) -> None:
        """Scale around the cursor."""
        factor = ZOOM_FACTOR if event.angleDelta().y() > 0 else 1 / ZOOM_FACTOR
        self.zoom_by(factor)

    def mousePressEvent(self, event: Any) -> None:
        """Start a pan when the press is not on a node."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.itemAt(event.position().toPoint()) is None
        ):
            pt = event.position().toPoint()
            self._pan_origin = pt
            self._press_origin = pt
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Move the scroll bars while panning."""
        if self._pan_origin is not None:
            self._begin_fast_interaction()
            current = event.position().toPoint()
            delta = current - self._pan_origin
            self._pan_origin = current
            horizontal = self.horizontalScrollBar()
            vertical = self.verticalScrollBar()
            horizontal.setValue(horizontal.value() - delta.x())
            vertical.setValue(vertical.value() - delta.y())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """End the pan, restore the cursor and detect background clicks."""
        if self._pan_origin is not None and self._press_origin is not None:
            moved = (
                event.position().toPoint() - self._press_origin
            ).manhattanLength()
            self._pan_origin = None
            self._press_origin = None
            self.unsetCursor()
            if moved <= 4:
                self.background_clicked.emit()
            return
        self._pan_origin = None
        self._press_origin = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
