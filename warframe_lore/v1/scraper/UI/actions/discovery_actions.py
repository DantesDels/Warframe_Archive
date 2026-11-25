"""Non-blocking discovery commands for the Atelier UI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any

from PySide6.QtWidgets import QMessageBox

from ...collect.language_purge import universe_allowed_languages
from ..runtime.discovery_runner import start_discovery


def apply_discovery(
    app: Any, universe: dict[str, Any], on_done: Callable[[int], None] | None = None
) -> int:
    """Start discovery off the main thread; completion is reported via callback."""
    settings = app.settings_store.load()
    uid = str(universe.get("id", ""))
    langs = universe_allowed_languages(app.workspace, uid)
    seeds = [
        str(source.get("location", "")).strip()
        for source in app.workspace.sources_for(uid)
        if str(source.get("location", "")).strip()
    ]
    settings = replace(
        settings, discovery_seeds=tuple(seeds), allowed_languages=langs
    )
    u_with_langs = {**universe, "allowed_languages": langs}
    start_discovery(app, u_with_langs, on_done, settings)
    return 0


def discover_selected(app: Any) -> None:
    universe = _selected_universe(app, "Découverte")
    if universe is None:
        return
    uid = str(universe["id"])
    apply_discovery(app, universe, lambda count: _notify(
        app, "Découverte",
        f"{count} nouveau(x) candidat(s) à partir de "
        f"{app.settings_store.load().min_relevance} % de pertinence.",
        uid,
    ))


def sync_selected(app: Any, universe_id: str | None = None) -> None:
    uid = universe_id or app.selected_id()
    universe = app.workspace.get(uid or "")
    if universe is None:
        QMessageBox.information(
            app, "Synchronisation", "Sélectionnez d'abord un Univers."
        )
        return
    apply_discovery(app, universe, lambda count: _notify(
        app, "Synchronisation",
        f"Synchronisation terminée pour {universe['name']} "
        f"({count} nouveaux candidats).",
        uid,
    ))


def sync_all(app: Any) -> None:
    universes = list(app.workspace.universes())
    _sync_next(app, universes, 0, 0)


def _sync_next(
    app: Any, universes: list[dict[str, Any]], index: int, total: int
) -> None:
    if index >= len(universes):
        app.refresh(app.selected_id())
        QMessageBox.information(
            app, "Synchronisation",
            f"Synchronisation terminée pour {len(universes)} Univers "
            f"({total} nouveaux candidats).",
        )
        return
    universe = universes[index]
    apply_discovery(
        app, universe,
        lambda count: _sync_next(app, universes, index + 1, total + count),
    )


def _selected_universe(app: Any, title: str) -> dict[str, Any] | None:
    universe = app.workspace.get(app.selected_id() or "")
    if universe is None:
        QMessageBox.information(app, title, "Sélectionnez d'abord un Univers.")
        return None
    return universe


def _notify(app: Any, title: str, message: str, uid: str | None) -> None:
    app.refresh(uid)
    QMessageBox.information(app, title, message)
