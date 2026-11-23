"""Service startup and shutdown helpers for the main Atelier window."""

from __future__ import annotations

from typing import Any


def start_graphql(app: Any) -> None:
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


def stop_services(app: Any) -> None:
    from ..runner_ui import cleanup_execution
    from .discovery_runner import cleanup_discovery

    cleanup_execution(app)
    cleanup_discovery(app)
    if app._graphql_handle is not None:
        app._graphql_handle.stop()
