"""Command handlers for the Atelier PySide6 window."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QMessageBox

from ..dialogs import prompt_universe_name
from ..dialogs.preflight_dialog import open_preflight
from ..dialogs.settings_io import open_settings
from .discovery_actions import (
    apply_discovery,
    discover_selected,
    sync_all,
    sync_selected,
)

__all__ = [
    "apply_discovery",
    "create_universe",
    "delete_selected",
    "discover_selected",
    "open_app_settings",
    "prepare_launch",
    "rename_universe",
    "sync_all",
    "sync_selected",
]


def open_app_settings(app: Any) -> None:
    open_settings(app, app.settings_store)


def create_universe(app: Any) -> None:
    name = prompt_universe_name(
        app,
        title="Nouvel Univers",
        used_names=set(cast(list[str], app.workspace.names())),
    )
    if name:
        universe = cast(dict[str, Any], app.workspace.create(name))
        apply_discovery(app, universe)
        app.refresh(str(universe["id"]))


def rename_universe(app: Any) -> None:
    universe = cast(dict[str, Any] | None, app.workspace.get(app.selected_id() or ""))
    if universe is None:
        QMessageBox.information(
            app, "Renommer", "Sélectionnez d'abord un Univers."
        )
        return
    name = prompt_universe_name(
        app,
        title="Renommer l'Univers",
        used_names=set(
            cast(list[str], app.workspace.names(exclude=str(universe["id"])))
        ),
        initial=str(universe.get("name", "")),
    )
    if name:
        app.workspace.rename(str(universe["id"]), name)
        apply_discovery(app, universe)
        app.refresh(str(universe["id"]))


def delete_selected(app: Any) -> None:
    uid = cast(str | None, app.selected_id())
    universe = cast(dict[str, Any] | None, app.workspace.get(uid or ""))
    if universe is None:
        QMessageBox.information(
            app, "Suppression", "Sélectionnez d'abord un Univers."
        )
        return
    question = f"Supprimer l'Univers « {universe['name']} » et toutes ses données ?"
    if (
        QMessageBox.question(app, "Suppression", question)
        == QMessageBox.StandardButton.Yes
    ):
        app.workspace.delete_universe(uid)
        app.refresh()


def prepare_launch(app: Any) -> None:
    uid = cast(str | None, app.selected_id())
    universe = cast(dict[str, Any] | None, app.workspace.get(uid or ""))
    if universe is None:
        QMessageBox.information(
            app, "Pré-exécution", "Sélectionnez d'abord un Univers."
        )
        return
    candidates = cast(list[dict[str, Any]],
        app.workspace.candidates_for(str(universe["id"])))
    active = [item for item in candidates if item.get("status") == "active"]
    plan = open_preflight(
        app, app.settings_store.load(), (universe["id"],), len(active)
    )
    if plan:
        app.last_plan = plan
        app.start_execution(plan)
