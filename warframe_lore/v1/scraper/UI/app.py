"""Native Atelier v1 window: Explorer-like Universe browser."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..settings import SettingsStore
from .actions import commands
from .dialogs import prompt_universe_name
from .execution import ExecutionPanel
from .theme import apply_theme
from .views import DetailPane, UniverseTree, toolbar
from .workspace import WorkshopWorkspace


class AtelierApp(ttk.Frame):
    """Left tree + right detail pane with grouped actions and live execution."""

    def __init__(self, master: tk.Tk, workspace=None) -> None:
        super().__init__(master, padding=10)
        apply_theme(master)
        self.settings_store = SettingsStore(Path("data/v1/settings.json"))
        self.workspace = workspace or WorkshopWorkspace()
        self.last_plan = None
        self.pack(fill="both", expand=True)
        bar = toolbar.build(self)
        self.status = ttk.Label(bar, text="", style="Muted.TLabel")
        self.status.pack(side="right", padx=(8, 2))
        self._build_browser()
        self.execution = ExecutionPanel(self)
        self.execution.pack(fill="x", pady=(8, 0))
        self.refresh()

    def _build_browser(self) -> None:
        panes = ttk.PanedWindow(self, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.tree = UniverseTree(panes, on_select=self.on_select)
        self.tree.view.bind("<F2>", lambda _event: self.rename_universe())
        self.details = DetailPane(panes)
        panes.add(self.tree, weight=1)
        panes.add(self.details, weight=3)

    def on_select(self, universe_id: str | None) -> None:
        self._show_details(universe_id)

    def _show_details(self, universe_id: str | None) -> None:
        self.details.show(
            self.workspace.get(universe_id) if universe_id else None,
            self.workspace,
            lambda: self.refresh(self.tree.selected_id()),
        )

    def refresh(self, selected_id: str | None = None) -> None:
        universes = self.workspace.universes()
        self.tree.set_universes(universes)
        self.status.configure(text=f"{len(universes)} Univers")
        if selected_id:
            self.tree.select(selected_id)
        self._show_details(self.tree.selected_id())

    def start_execution(self, plan) -> None:
        self.last_plan = plan
        self.execution.run(plan)

    def create_universe(self) -> None:
        name = prompt_universe_name(
            self, title="Nouvel Univers", used_names=self.workspace.names(),
        )
        if name:
            universe = self.workspace.create(name)
            commands.apply_discovery(self, universe)
            self.refresh(universe["id"])

    def rename_universe(self) -> None:
        universe = self.workspace.get(self.tree.selected_id() or "")
        if universe is None:
            messagebox.showinfo("Renommer", "Sélectionnez d'abord un Univers.")
            return
        name = prompt_universe_name(
            self,
            title="Renommer l'Univers",
            used_names=self.workspace.names(exclude=universe["id"]),
            initial=universe["name"],
        )
        if name:
            self.workspace.rename(universe["id"], name)
            commands.apply_discovery(self, universe)
            self.refresh(universe["id"])
