"""Optional local GraphQL server for the v1 workspace."""

from __future__ import annotations

import threading
from typing import Any


class GraphQLServerHandle:
    """Handle used to stop the background GraphQL server."""

    def __init__(self, server: Any, thread: threading.Thread, url: str) -> None:
        self.server = server
        self.thread = thread
        self.url = url

    def stop(self) -> None:
        """Signal the server to exit and join its thread."""
        try:
            self.server.should_exit = True
        except AttributeError:
            pass
        self.thread.join(timeout=2)


def start_graphql_server(
    workspace: Any, *, host: str = "127.0.0.1", port: int = 8765
) -> GraphQLServerHandle:
    """Serve the workspace graph on localhost in a daemon thread."""
    import uvicorn
    from fastapi import FastAPI
    from strawberry.fastapi import GraphQLRouter

    from .schema import build_schema

    app = FastAPI(title="Atelier v1 GraphQL")
    app.include_router(GraphQLRouter(build_schema(workspace)), prefix="/graphql")
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://{host}:{port}/graphql"
    return GraphQLServerHandle(server, thread, url)
