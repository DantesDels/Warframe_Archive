"""``cephalon ui`` interface — HTTP server launcher.

Startup glue: builds the ``LoreStore`` (megafiles ``out/*.json``), the
``MediaIndex`` (wiki images) and the ``ApiHandler`` (``/api/*`` routes +
static files, Gzip), then serves on ``127.0.0.1``.

Launch: ``python -m warframe_lore.ui.server`` (PyInstaller exe) or
``cephalon ui`` (CLI).  Options: ``--out``, ``--port``, ``--no-browser``.
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from http.server import ThreadingHTTPServer
from pathlib import Path

from ..media import MediaIndex
from .handlers import ApiHandler
from .store import LoreStore

__all__ = ["LoreStore", "serve_forever", "main"]


def _bundle_root() -> Path:
    """Root of the unpacked PyInstaller files (``sys._MEIPASS``)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent


def _static_dir() -> Path:
    """Static files directory (source, sdist or PyInstaller exe)."""
    root = _bundle_root()
    for candidate in (
        root / "warframe_lore" / "ui" / "static",   # exe onefile --add-data
        root / "static",                            # paquet installé / source
        Path(__file__).resolve().parent / "static",
    ):
        if candidate.is_dir():
            return candidate
    return root


def _default_output_dir() -> Path:
    """Megafile folder to expose: ``out/`` of the cwd, project or exe."""
    exe_dir = (Path(sys.executable).resolve().parent
               if getattr(sys, "frozen", False) else None)
    candidates = [
        Path.cwd() / "out",
        Path(__file__).resolve().parent.parent.parent / "out",
        *( [exe_dir / "out"] if exe_dir else [] ),
        _bundle_root() / "out",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _build_handler(store: LoreStore, media: MediaIndex | None = None) -> type[ApiHandler]:
    ApiHandler.store = store
    ApiHandler.media = media
    ApiHandler.root = _static_dir()
    return ApiHandler


def serve_forever(output_dir: Path, port: int = 0,
                  open_browser: bool = True) -> None:
    """Start the server (blocking). Used by ``cephalon ui``.

    Args:
        output_dir: folder of the megafiles to expose.
        port: port to use (0 = automatically free port).
        open_browser: open the default browser after startup.
    """
    store = LoreStore(output_dir)
    media = MediaIndex(output_dir, cache_dir="cache/public_export/media")
    handler = _build_handler(store, media)
    try:
        threading.Thread(target=media.ensure, daemon=True).start()
    except RuntimeError:  # no thread available: build on first call
        pass
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    actual_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    print(f"Cephalon UI — interface available at {url}")
    print(f"  Data source: {output_dir.resolve()}")
    print("  Press Ctrl+C to stop the server.")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Cephalon UI.")
    finally:
        httpd.server_close()
        print("Server stopped.")


def main(argv: list[str] | None = None) -> int:
    """Console entry point ``cephalon-ui`` (standalone, for the PyInstaller exe)."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="cephalon-ui",
        description="Web interface to browse scraped Warframe lore.",
    )
    parser.add_argument("--out", type=Path, default=None,
                        help="Megafiles folder (default: ./out)")
    parser.add_argument("--port", type=int, default=0,
                        help="Port to use (0 = free, default)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Does not open the browser automatically.")
    args = parser.parse_args(argv)

    output_dir = args.out or _default_output_dir()
    if not output_dir.is_dir():
        print(f"Warning: no data folder found ({output_dir}).")
        print("Run `cephalon run` first to generate the megafiles.")
    serve_forever(output_dir, port=args.port,
                  open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())