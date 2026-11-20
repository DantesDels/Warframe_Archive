"""Toolbar command handlers for the Atelier v1 window."""

from __future__ import annotations

from tkinter import messagebox

from ...discovery import discover
from ..dialogs.preflight_dialog import open_preflight
from ..dialogs.settings_dialog import open_settings


def apply_discovery(app, universe: dict) -> int:
    """Refresh candidates for one Universe using the configured threshold."""
    threshold = app.settings_store.load().min_relevance
    candidates = discover(universe, threshold)
    app.workspace.set_candidates(candidates)
    return len(candidates)


def open_app_settings(app) -> None:
    """Edit and persist the default execution settings."""
    open_settings(app, app.settings_store)


def discover_selected(app) -> None:
    """Run discovery for the selected Universe and report the outcome."""
    universe_id = app.tree.selected_id()
    universe = app.workspace.get(universe_id or "")
    if universe is None:
        messagebox.showinfo("Découverte", "Sélectionnez d'abord un Univers.")
        return
    count = apply_discovery(app, universe)
    app.refresh(universe_id)
    threshold = app.settings_store.load().min_relevance
    messagebox.showinfo(
        "Découverte",
        f"{count} candidat(s) retenu(s) à partir de {threshold} % de pertinence.",
    )


def delete_selected(app) -> None:
    """Remove the selected Universe after explicit confirmation."""
    universe_id = app.tree.selected_id()
    universe = app.workspace.get(universe_id or "")
    if universe is None:
        messagebox.showinfo("Suppression", "Sélectionnez d'abord un Univers.")
        return
    question = f"Supprimer l'Univers « {universe['name']} » et toutes ses données ?"
    if messagebox.askyesno("Suppression", question):
        app.workspace.delete_universe(universe_id)
        app.refresh()


def prepare_launch(app) -> None:
    """Collect the pre-execution plan for the selected Universe."""
    universe_id = app.tree.selected_id()
    universe = app.workspace.get(universe_id or "")
    if universe is None:
        messagebox.showinfo("Pré-exécution", "Sélectionnez d'abord un Univers.")
        return
    active = [
        item
        for item in app.workspace.candidates_for(universe["id"])
        if item["status"] == "active"
    ]
    plan = open_preflight(
        app,
        app.settings_store.load(),
        (universe["id"],),
        len(active),
    )
    if plan:
        app.last_plan = plan
        if hasattr(app, "start_execution"):
            app.start_execution(plan)
        else:
            messagebox.showinfo(
                "Pré-exécution",
                "Plan validé : le moteur d'exécution sera branché à la tranche S4.",
            )
