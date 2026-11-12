"""Static assets and single-page-app routes of the local UI.

Single responsibility: map a request path to the static file to serve — the fixed
assets of the root application, and the two autonomous Vue builds
(``/inspector/`` and ``/timeline/``) whose hashed assets live in their own folder.
ONE rule for both SPAs: they differ only by prefix and folder.
"""

from __future__ import annotations

# Fixed assets of the root application: path -> (file, content type).
STATIC_ROUTES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/styles.css": ("styles.css", "text/css"),
    "/vendor/vue-flow.bundle.js": ("vendor/vue-flow.bundle.js",
                                   "text/javascript"),
    "/vendor/vue-flow.bundle.css": ("vendor/vue-flow.bundle.css", "text/css"),
}

# Autonomous Vue builds: URL prefix -> folder under ``static/``.
SPA_PREFIXES = (("/inspector/", "inspector"), ("/timeline/", "timeline"))

# Content type by asset extension (HTML otherwise).
ASSET_TYPES = ((".js", "text/javascript"), (".css", "text/css"))


def static_route(path: str) -> tuple[str, str] | None:
    """Fixed asset serving ``path``, or ``None`` when it is not one."""
    return STATIC_ROUTES.get(path)


def spa_route(path: str) -> tuple[str, str] | None:
    """SPA file serving ``path`` as ``(relative file, content type)``.

    ``/inspector/`` serves its ``index.html``; the hashed assets are served from
    the same folder (``/inspector/assets/app-xyz.js``).
    """
    for prefix, folder in SPA_PREFIXES:
        if not path.startswith(prefix):
            continue
        relative = path[len(prefix):] or "index.html"
        return f"{folder}/{relative}", asset_type(relative)
    return None


def asset_type(relative: str) -> str:
    """Content type of a static asset (HTML by default)."""
    for suffix, content_type in ASSET_TYPES:
        if relative.endswith(suffix):
            return content_type
    return "text/html"


__all__ = ["ASSET_TYPES", "SPA_PREFIXES", "STATIC_ROUTES", "asset_type",
           "spa_route", "static_route"]
