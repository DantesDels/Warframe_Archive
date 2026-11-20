"""Left-hand Universe tree, styled like Windows Explorer's navigation pane."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class UniverseTree(ttk.Frame):
    """Explorer-like tree listing every Universe under a single root."""

    def __init__(self, parent: tk.Misc, on_select) -> None:
        super().__init__(parent, padding=(6, 4))
        self.on_select = on_select
        self.view = ttk.Treeview(self, show="tree", selectmode="browse")
        self.view.pack(fill="both", expand=True)
        self.view.bind("<<TreeviewSelect>>", self._notify)
        self._root = self.view.insert("", "end", text="Univers", open=True)

    def set_universes(self, universes: list[dict]) -> None:
        for child in self.view.get_children(self._root):
            self.view.delete(child)
        for universe in universes:
            self.view.insert(
                self._root,
                "end",
                iid=universe["id"],
                text=universe["name"],
            )

    def select(self, universe_id: str) -> None:
        self.view.selection_set(universe_id)

    def selected_id(self) -> str | None:
        selection = self.view.selection()
        return selection[0] if selection else None

    def _notify(self, _event: tk.Event) -> None:
        self.on_select(self.selected_id())
