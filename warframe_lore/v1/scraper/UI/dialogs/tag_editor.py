"""Interactive add/remove tag chip editor for per-universe topic filtering."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...capabilities.modes import parse_tags

_CHIPS_PER_ROW = 4


class TagEditor(QWidget):
    """Allow users to add tags and remove any tag individually or clear all."""

    def __init__(
        self, initial_tags: list[str] | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._tags: list[str] = parse_tags(initial_tags or [])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Ex. Lore, Quests, Characters (Entrée ou + Ajouter)"
        )
        self.input.returnPressed.connect(self._add_from_input)
        self.add_button = QPushButton("+ Ajouter")
        self.add_button.setAutoDefault(False)
        self.add_button.clicked.connect(self._add_from_input)
        self.clear_button = QPushButton("Tout effacer")
        self.clear_button.setAutoDefault(False)
        self.clear_button.clicked.connect(self.clear_tags)
        row.addWidget(self.input, 1)
        row.addWidget(self.add_button)
        row.addWidget(self.clear_button)
        layout.addLayout(row)
        self._chips_box = QWidget()
        self._chips_layout = QGridLayout(self._chips_box)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        layout.addWidget(self._chips_box)
        self._rebuild_chips()

    def _add_from_input(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        self.add_tags(text)
        self.input.clear()

    def add_tags(self, raw: str | list[str]) -> list[str]:
        """Add one or more tags (deduplicated) and refresh the chip list."""
        merged = self._tags + parse_tags(raw)
        self._tags = parse_tags(merged)
        self._rebuild_chips()
        return list(self._tags)

    def remove_tag(self, tag: str) -> None:
        """Remove a single tag (case-insensitive) and refresh the chip list."""
        key = tag.strip().casefold()
        self._tags = [item for item in self._tags if item.casefold() != key]
        self._rebuild_chips()

    def clear_tags(self) -> None:
        """Remove all tags and clear the input box."""
        self._tags = []
        self.input.clear()
        self._rebuild_chips()

    def tags(self) -> list[str]:
        """Return all saved chips merged with any unsubmitted input text."""
        pending = parse_tags(self.input.text())
        return parse_tags(self._tags + pending)

    def _rebuild_chips(self) -> None:
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.clear_button.setEnabled(bool(self._tags))
        if not self._tags:
            hint = QLabel(
                "Aucun tag actif. Utilisez « + Ajouter » pour cibler un thème."
            )
            hint.setObjectName("MutedHint")
            hint.setWordWrap(True)
            self._chips_layout.addWidget(hint, 0, 0, 1, _CHIPS_PER_ROW)
            return
        for idx, tag in enumerate(self._tags):
            chip = QPushButton(f"{tag}  ×")
            chip.setObjectName("TagChip")
            chip.setAutoDefault(False)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(f"Cliquer pour supprimer le tag « {tag} »")
            chip.clicked.connect(lambda _checked=False, t=tag: self.remove_tag(t))
            row, col = divmod(idx, _CHIPS_PER_ROW)
            self._chips_layout.addWidget(chip, row, col)
