"""Service startup and shutdown helpers for the main Atelier window."""

from __future__ import annotations

from typing import Any


def start_graphql(app: Any) -> None:
    """Start background GraphQL API (if enabled) and cooperative watch scheduler."""
    _start_watch_scheduler(app)
    settings = app.settings_store.load()
    if not settings.graph_api_enabled:
        return
    try:
        from ...graph.server import start_graphql_server

        app._graphql_handle = start_graphql_server(
            app.workspace,
            host=settings.graph_api_host,
            port=settings.graph_api_port,
        )
    except Exception as error:  # noqa: BLE001
        app.status_bar.showMessage(f"GraphQL indisponible : {error}")


def _start_watch_scheduler(app: Any) -> None:
    try:
        from ...watch import LocalWatchScheduler

        scheduler = LocalWatchScheduler(app.workspace, tick_seconds=60.0)
        scheduler.start()
        app._watch_scheduler = scheduler
    except Exception:  # noqa: BLE001
        app._watch_scheduler = None


def stop_services(app: Any) -> None:
    """Stop active execution, discovery, watch scheduler and GraphQL server."""
    from ..runner_ui import cleanup_execution
    from .discovery_runner import cleanup_discovery

    cleanup_execution(app)
    cleanup_discovery(app)
    scheduler = getattr(app, "_watch_scheduler", None)
    if scheduler is not None:
        scheduler.stop()
        app._watch_scheduler = None
    gaps_srv = getattr(getattr(app, "workspace", None), "_gaps_server", None)
    if gaps_srv is not None:
        gaps_srv.stop()
        app.workspace._gaps_server = None
    if app._graphql_handle is not None:
        app._graphql_handle.stop()
