"""Modal name prompts used to create or rename a Universe."""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox, QWidget


def prompt_universe_name(
    parent: QWidget | None,
    *,
    title: str,
    used_names: set[str],
    initial: str = "",
) -> str | None:
    """Return a unique trimmed name, or None when cancelled."""
    current = initial
    while True:
        answer, ok = QInputDialog.getText(
            parent,
            title,
            "Nom de l'Univers :",
            text=current,
        )
        if not ok:
            return None
        name = answer.strip()
        if not name:
            QMessageBox.critical(
                parent,
                title,
                "Le nom de l'Univers ne peut pas être vide.",
            )
        elif name.casefold() in used_names:
            QMessageBox.critical(parent, title, "Ce nom d'Univers existe déjà.")
        else:
            return name
        current = name
