"""Grouped toolbar builder for the Atelier v1 window."""

from __future__ import annotations

from tkinter import ttk

from ..actions import commands
from ..theme import Tooltip


def build(app) -> ttk.Frame:
    """Create and attach the grouped action toolbar."""
    toolbar = ttk.Frame(app, style="Panel.TFrame", padding=(6, 4))
    toolbar.pack(fill="x", pady=(0, 8))
    _group(toolbar, "Univers", [
        ("Nouvel Univers", app.create_universe, ""),
        ("Renommer (F2)", app.rename_universe, ""),
        ("Supprimer", lambda: commands.delete_selected(app),
         "Supprime l'Univers sélectionné."),
    ])
    _separator(toolbar)
    _group(toolbar, "Pipeline", [
        ("Découvrir des sources", lambda: commands.discover_selected(app), ""),
        ("Pré-exécution / Lancer…", lambda: commands.prepare_launch(app), ""),
    ])
    _separator(toolbar)
    _group(toolbar, "Application", [
        ("Actualiser", app.refresh, "Recharge l'arborescence et les compteurs."),
        ("Paramètres", lambda: commands.open_app_settings(app),
         "Seuil n %, formats de sortie et règles de sécurité d'import."),
    ])
    return toolbar


def _group(parent, title: str, items) -> None:
    group = ttk.Frame(parent, style="Panel.TFrame")
    group.pack(side="left", padx=(0, 6))
    ttk.Label(group, text=title, style="Muted.TLabel").pack(
        side="left", padx=(0, 6),
    )
    for label, command, tip in items:
        button = ttk.Button(group, text=label, command=command)
        button.pack(side="left", padx=(0, 4))
        if tip:
            Tooltip(button, tip)


def _separator(parent) -> None:
    ttk.Separator(parent, orient="vertical").pack(
        side="left", fill="y", padx=6, pady=2,
    )
