"""Settings dialog open/save helpers."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ...settings.store import SettingsStore
from .settings_dialog import SettingsDialog


def open_settings(parent: QWidget | None, store: SettingsStore):
    dialog = SettingsDialog(parent, store)
    dialog.exec()
    return dialog.result
