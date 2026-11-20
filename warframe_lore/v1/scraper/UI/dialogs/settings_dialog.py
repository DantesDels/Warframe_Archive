"""Settings dialog for default execution parameters."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from ...settings.models import OUTPUT_FORMATS, Settings
from ...settings.store import SettingsStore


class OptionsFrame(ttk.Frame):
    """Reusable threshold / formats / RAG controls."""

    def __init__(self, parent: tk.Misc, settings: Settings) -> None:
        super().__init__(parent)
        self._relevance = tk.IntVar(value=settings.min_relevance)
        self._rag = tk.BooleanVar(value=settings.rag_coupling)
        self._formats = {
            name: tk.BooleanVar(value=name in settings.output_formats)
            for name in OUTPUT_FORMATS
        }
        ttk.Label(self, text="Score de pertinence minimal (%)").pack(anchor="w")
        ttk.Spinbox(
            self, from_=0, to=100, textvariable=self._relevance, width=8,
        ).pack(anchor="w", pady=(2, 10))
        ttk.Label(self, text="Formats de sortie").pack(anchor="w")
        choices = ttk.Frame(self)
        choices.pack(fill="x", pady=(2, 10))
        for name, variable in self._formats.items():
            ttk.Checkbutton(
                choices, text=name.upper(), variable=variable,
            ).pack(side="left", padx=(0, 8))
        ttk.Checkbutton(
            self,
            text="Couplage RAG (découpage en chunks / préparation RAG)",
            variable=self._rag,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(self, text="Règles de sécurité d'import").pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Blocage systématique : scripts/contenus actifs, macros, "
                "archives, images non analysées (QR) et formats à risque."
            ),
            foreground="#68738a",
            wraplength=420,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

    def settings(self) -> Settings:
        """Build a validated ``Settings`` from the current controls."""
        formats = tuple(
            name for name, variable in self._formats.items() if variable.get()
        )
        return Settings(self._relevance.get(), formats, self._rag.get())


class SettingsDialog(tk.Toplevel):
    """Modal editor persisted through ``SettingsStore``."""

    def __init__(self, parent: tk.Misc, store: SettingsStore) -> None:
        super().__init__(parent)
        self.title("Paramètres")
        self.resizable(False, False)
        self.store = store
        self.result: Settings | None = None
        self.options = OptionsFrame(self, store.load())
        self.options.pack(fill="x", padx=16, pady=(16, 6))
        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=16, pady=(10, 16))
        ttk.Button(buttons, text="Annuler", command=self.destroy).pack(side="right")
        ttk.Button(
            buttons, text="Enregistrer", command=self._save,
        ).pack(side="right", padx=6)
        self.grab_set()

    def _save(self) -> None:
        try:
            settings = self.options.settings()
        except ValueError as error:
            messagebox.showerror("Paramètres", str(error), parent=self)
            return
        self.store.save(settings)
        self.result = settings
        self.destroy()


def open_settings(parent: tk.Misc, store: SettingsStore) -> Settings | None:
    """Show the dialog and return the saved settings, if any."""
    dialog = SettingsDialog(parent, store)
    parent.wait_window(dialog)
    return dialog.result
