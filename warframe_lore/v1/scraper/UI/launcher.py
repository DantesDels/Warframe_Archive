"""Standalone entry point for the packaged native v1 UI."""

from __future__ import annotations

import tkinter as tk

from warframe_lore.v1.scraper.UI.app import AtelierApp

WINDOW_TITLE = "Atelier v1 — Univers"
WINDOW_SIZE = "1100x680"
MINIMUM_SIZE = (820, 520)


def main() -> None:
    """Open the Atelier v1 desktop window."""
    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry(WINDOW_SIZE)
    root.minsize(*MINIMUM_SIZE)
    AtelierApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
