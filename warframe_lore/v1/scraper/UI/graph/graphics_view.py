"""QGraphicsView with wheel zoom, button zoom and drag-to-pan on dark canvas."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsView

ZOOM_FACTOR = 1.18


class GraphGraphicsView(QGraphicsView):
    """Zoom with the wheel or toolbar, pan by dragging the dark background."""

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#0f172a")))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self._pan_origin: QPoint | None = None

    def zoom_by(self, factor: float) -> None:
        """Apply a zoom multiplier while clamping extreme scale values."""
        current = self.transform().m11()
        if (factor > 1 and current > 6.0) or (factor < 1 and current < 0.1):
            return
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
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Move the scroll bars while panning."""
        if self._pan_origin is not None:
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
        """End the pan and restore the cursor."""
        self._pan_origin = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)
