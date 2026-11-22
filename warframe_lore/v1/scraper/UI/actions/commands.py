"""Command handlers for the Atelier PySide6 window."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ...discovery import discover
from ..dialogs.preflight_dialog import open_preflight
from ..dialogs.settings_dialog import open_settings


def apply_discovery(app, universe: dict) -> int:
    threshold = app.settings_store.load().min_relevance
    candidates = discover(universe, threshold)
    # keep existing manual/active sources; merge discovered as candidates
    existing = {c["location"] for c in app.workspace.candidates_for(universe["id"])}
    new_candidates = [c for c in candidates if c.location not in existing]
    merged = list(app.workspace.candidates_for(universe["id"]))
    for item in new_candidates:
        merged.append({
            "id": item.id,
            "universeId": item.universe_id,
            "kind": item.kind,
            "location": item.location,
            "title": item.title,
            "score": item.score,
            "proof": item.proof,
            "discoveredBy": item.discovered_by,
            "status": item.status,
            "forceUpdate": item.force_update,
        })
    kept = [c for c in merged if c["universeId"] != universe["id"]]
    kept.extend(c for c in merged if c["universeId"] == universe["id"])
    app.workspace.data["candidates"] = kept
    app.workspace.save()
    return len(new_candidates)


def open_app_settings(app) -> None:
    open_settings(app, app.settings_store)


def discover_selected(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "D?couverte", "S?lectionnez d'abord un Univers."
        )
        return
    count = apply_discovery(app, universe)
    app.refresh(uid)
    threshold = app.settings_store.load().min_relevance
    QMessageBox.information(
        app, "D?couverte",
        f"{count} nouveau(x) candidat(s) ? partir de {threshold} % de pertinence.",
    )


def delete_selected(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Suppression", "S?lectionnez d'abord un Univers."
        )
        return
    question = f"Supprimer l'Univers ? {universe['name']} ? et toutes ses donn?es ?"
    if QMessageBox.question(app, "Suppression", question) == QMessageBox.Yes:
        app.workspace.delete_universe(uid)
        app.refresh()


def prepare_launch(app) -> None:
    uid = app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Pr?-ex?cution", "S?lectionnez d'abord un Univers."
        )
        return
    active = [
        item for item in app.workspace.candidates_for(universe["id"])
        if item.get("status") == "active"
    ]
    plan = open_preflight(
        app, app.settings_store.load(), (universe["id"],), len(active)
    )
    if plan:
        app.last_plan = plan
        app.start_execution(plan)


def sync_selected(app, universe_id: str | None = None) -> None:
    uid = universe_id or app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Synchronisation", "S?lectionnez d'abord un Univers."
        )
        return
    count = apply_discovery(app, universe)
    app.refresh(uid)
    QMessageBox.information(
        app, "Synchronisation",
        (
            f"Synchronisation termin?e pour {universe['name']} "
            f"({count} nouveaux candidats)."
        ),
    )


def sync_all(app) -> None:
    universes = app.workspace.universes()
    total = 0
    for universe in universes:
        total += apply_discovery(app, universe)
    app.refresh(app.selected_id())
    QMessageBox.information(
        app, "Synchronisation",
        (
            f"Synchronisation termin?e pour {len(universes)} Univers "
            f"({total} nouveaux candidats)."
        ),
    )
