"""Standalone entry point for the packaged PySide6 v1 UI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from warframe_lore.v1.scraper.UI.app import AtelierApp
from warframe_lore.v1.scraper.UI.style import apply_theme


def main() -> None:
    """Open the Atelier v1 desktop window."""
    app_obj = QApplication.instance()
    app = app_obj if isinstance(app_obj, QApplication) else QApplication(sys.argv)
    apply_theme()
    window = AtelierApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
