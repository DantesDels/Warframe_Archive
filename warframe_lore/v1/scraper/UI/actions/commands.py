"""Command handlers for the Atelier PySide6 window."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ...discovery import discover
from ..dialogs.preflight_dialog import open_preflight
from ..dialogs.settings_dialog import open_settings


def apply_discovery(app, universe: dict) -> int:
    threshold = app.settings_store.load().min_relevance
    candidates = discover(universe, threshold)
    app.workspace.set_candidates(candidates)
    return len(candidates)


def open_app_settings(app) -> None:
    open_settings(app, app.settings_store)


def discover_selected(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Découverte", "Sélectionnez d'abord un Univers.",
        )
        return
    count = apply_discovery(app, universe)
    app.refresh(uid)
    threshold = app.settings_store.load().min_relevance
    QMessageBox.information(
        app,
        "Découverte",
        f"{count} candidat(s) retenu(s) à partir de {threshold} % de pertinence.",
    )


def delete_selected(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Suppression", "Sélectionnez d'abord un Univers.",
        )
        return
    question = (
        f"Supprimer l'Univers « {universe['name']} » et toutes ses données ?"
    )
    if QMessageBox.question(app, "Suppression", question) == QMessageBox.Yes:
        app.workspace.delete_universe(uid)
        app.refresh()


def prepare_launch(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Pré-exécution", "Sélectionnez d'abord un Univers.",
        )
        return
    active = [
        item
        for item in app.workspace.candidates_for(universe["id"])
        if item.get("status") == "active"
    ]
    plan = open_preflight(
        app, app.settings_store.load(), (universe["id"],), len(active),
    )
    if plan:
        app.last_plan = plan
        app.start_execution(plan)


def sync_selected(app, universe_id: str | None = None) -> None:
    uid = universe_id or app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Synchronisation", "Sélectionnez d'abord un Univers."
        )
        return
    count = apply_discovery(app, universe)
    app.refresh(uid)
    QMessageBox.information(
        app,
        "Synchronisation",
        f"Synchronisation terminée pour {universe['name']} ({count} candidats).",
    )


def sync_all(app) -> None:
    universes = app.workspace.universes()
    total = 0
    for universe in universes:
        total += apply_discovery(app, universe)
    app.refresh(app.selected_id())
    message = (
        f"Synchronisation terminée pour {len(universes)} Univers "
        f"({total} candidats)."
    )
    QMessageBox.information(app, "Synchronisation", message)
