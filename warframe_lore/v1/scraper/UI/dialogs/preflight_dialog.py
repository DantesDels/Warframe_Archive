"""Pre-execution dialog collecting the launch plan."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...settings.models import LaunchPlan, Settings
from .settings_dialog import OptionsFrame


class PreflightDialog(tk.Toplevel):
    """Ask for the final thresholds before launching a scrape."""

    def __init__(
        self,
        parent: tk.Misc,
        settings: Settings,
        universe_ids: tuple[str, ...],
        candidate_count: int,
    ) -> None:
        super().__init__(parent)
        self.title("Pré-exécution")
        self.resizable(False, False)
        self.universe_ids = universe_ids
        self.result: LaunchPlan | None = None
        summary = f"{len(universe_ids)} Univers • {candidate_count} candidats actifs"
        ttk.Label(self, text=summary).pack(anchor="w", padx=16, pady=(14, 8))
        self.options = OptionsFrame(self, settings)
        self.options.pack(fill="x", padx=16, pady=(0, 6))
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=16, pady=(6, 16))
        ttk.Button(buttons, text="Annuler", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons, text="Lancer", command=self._launch,
        ).pack(side="right", padx=6)
        self.grab_set()

    def _launch(self) -> None:
        try:
            settings = self.options.settings()
        except ValueError as error:
            messagebox.showerror("Pré-exécution", str(error), parent=self)
            return
        self.result = LaunchPlan(settings, self.universe_ids)
        self.destroy()


def open_preflight(
    parent: tk.Misc,
    settings: Settings,
    universe_ids: tuple[str, ...],
    candidate_count: int,
) -> LaunchPlan | None:
    """Show the dialog and return the validated launch plan, if any."""
    dialog = PreflightDialog(parent, settings, universe_ids, candidate_count)
    parent.wait_window(dialog)
    return dialog.result
