"""Modal name prompts used to create or rename a Universe."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog


def prompt_universe_name(
    parent: tk.Misc,
    *,
    title: str,
    used_names: set[str],
    initial: str = "",
) -> str | None:
    """Return a unique trimmed name, or None when the user cancels."""
    while True:
        answer = simpledialog.askstring(
            title,
            "Nom de l'Univers :",
            parent=parent,
            initialvalue=initial,
        )
        if answer is None:
            return None
        name = answer.strip()
        if not name:
            messagebox.showerror(title, "Le nom de l'Univers ne peut pas être vide.")
        elif name.casefold() in used_names:
            messagebox.showerror(title, "Ce nom d'Univers existe déjà.")
        else:
            return name
        initial = name
