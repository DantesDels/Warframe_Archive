"""Standalone entry point for the packaged PySide6 v1 UI."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from warframe_lore.v1.scraper.UI.app import AtelierApp


def main() -> None:
    """Open the Atelier v1 desktop window."""
    app = QApplication.instance() or QApplication(sys.argv)
    window = AtelierApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
