"""Right-hand detail pane: only the selected Universe's content is rendered."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..formatting import display_universe_status
from . import tabs


class DetailPane(ttk.Frame):
    """Explorer-style detail view driven by the current selection."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, padding=(14, 8))
        self.title_label = ttk.Label(self, font=("Segoe UI", 16, "bold"))
        self.subtitle_label = ttk.Label(self, foreground="#68738a")
        self.body = ttk.Frame(self)
        self.title_label.pack(anchor="w")
        self.subtitle_label.pack(anchor="w", pady=(2, 12))
        self.body.pack(fill="both", expand=True)
        self.clear()

    def clear(self) -> None:
        """Show the empty state until a Universe is selected."""
        self.title_label.configure(text="Aucun Univers sélectionné")
        self.subtitle_label.configure(
            text="Sélectionnez un Univers dans l'arborescence.",
        )
        for child in self.body.winfo_children():
            child.destroy()
        ttk.Label(
            self.body,
            text="Les détails (sources, documents, exécutions) apparaîtront ici.",
            foreground="#68738a",
        ).pack(expand=True)

    def show(self, universe, workspace, on_change) -> None:
        """Render the four data tabs for one Universe only."""
        if universe is None:
            self.clear()
            return
        self.title_label.configure(text=universe["name"])
        status = display_universe_status(universe["status"])
        self.subtitle_label.configure(
            text=f"{universe['description']}  •  {status}",
        )
        for child in self.body.winfo_children():
            child.destroy()
        notebook = ttk.Notebook(self.body)
        notebook.pack(fill="both", expand=True)
        tabs.add_sources_tab(notebook, workspace, universe, on_change)
        tabs.add_documents_tab(notebook, workspace, universe)
        tabs.add_runs_tab(notebook, workspace, universe)
        tabs.add_candidates_tab(notebook, workspace, universe, on_change)
