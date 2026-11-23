"""Command handlers for the Atelier PySide6 window."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QMessageBox

from ...collect.http import HttpClient
from ...settings.models import Settings
from ...use_cases.discover_universe import discover_universe
from ..dialogs.preflight_dialog import open_preflight
from ..dialogs.settings_io import open_settings


def apply_discovery(app: Any, universe: dict[str, Any]) -> int:
    settings = app.settings_store.load()
    # seed discovery from existing source locations (generic, universe-driven)
    seeds = [
        str(s.get("location", "")).strip()
        for s in app.workspace.sources_for(str(universe.get("id", "")))
        if str(s.get("location", "")).strip()
    ]
    settings = Settings(
        settings.min_relevance,
        settings.output_formats,
        settings.rag_coupling,
        settings.max_pages_per_source,
        settings.max_depth,
        settings.same_host_only,
        settings.use_cache,
        settings.incremental,
        settings.expand_manifests,
        settings.max_manifest_urls,
        settings.discovery_sitemaps,
        settings.discovery_feeds,
        settings.discovery_web_search,
        settings.discovery_web_search_url,
        settings.discovery_git,
        settings.discovery_wiki,
        tuple(seeds),
        settings.discovery_max_candidates,
        settings.review_child_pages,
        settings.use_playwright,
        settings.max_concurrency,
        settings.per_host_concurrency,
        settings.per_host_delay,
        settings.max_retries,
    )
    new_candidates = discover_universe(
        app.workspace, universe, settings, client=HttpClient()
    )
    return len(new_candidates)


def open_app_settings(app: Any) -> None:
    open_settings(app, app.settings_store)


def discover_selected(app: Any) -> None:
    uid = cast(str | None, app.selected_id())
    universe = cast(dict[str, Any] | None, app.workspace.get(uid or ""))
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


def delete_selected(app: Any) -> None:
    uid = cast(str | None, app.selected_id())
    universe = cast(dict[str, Any] | None, app.workspace.get(uid or ""))
    if universe is None:
        QMessageBox.information(
            app, "Suppression", "S?lectionnez d'abord un Univers."
        )
        return
    question = (
        f"Supprimer l'Univers « {universe['name']} » et toutes ses données ?"
    )
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
            app, "Pr?-ex?cution", "S?lectionnez d'abord un Univers."
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


def sync_selected(app: Any, universe_id: str | None = None) -> None:
    uid = universe_id or cast(str | None, app.selected_id())
    universe = cast(dict[str, Any] | None, app.workspace.get(uid or ""))
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


def sync_all(app: Any) -> None:
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
