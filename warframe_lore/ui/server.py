"""Interface ``cephalon ui`` — lancement du serveur HTTP.

Glue de démarrage : construit le ``LoreStore`` (megafiles ``out/*.json``), le
``MediaIndex`` (images wiki) et le ``ApiHandler`` (routes ``/api/*`` +
statiques, Gzip), puis sert en boucle sur ``127.0.0.1``.

Lancement : ``python -m warframe_lore.ui.server`` (exe PyInstaller) ou
``cephalon ui`` (CLI).  Paramètres : ``--out``, ``--port``, ``--no-browser``.
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
    """Racine des fichiers dépaquetés PyInstaller (``sys._MEIPASS``)."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else Path(__file__).resolve().parent


def _static_dir() -> Path:
    """Répertoire des fichiers statiques (source, sdist ou exe PyInstaller)."""
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
    """Dossier de megafiles à exposer : ``out/`` du cwd, du projet ou exe."""
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
    """Démarre le serveur (bloquant). Utilisé par ``cephalon ui``.

    Args:
        output_dir: dossier des megafiles à exposer.
        port: port à utiliser (0 = port libre automatique).
        open_browser: ouvrir le navigateur par défaut après démarrage.
    """
    store = LoreStore(output_dir)
    media = MediaIndex(output_dir, cache_dir="cache/public_export/media")
    handler = _build_handler(store, media)
    try:
        threading.Thread(target=media.ensure, daemon=True).start()
    except RuntimeError:  # pas de thread disponible : construction au 1er appel
        pass
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    actual_port = httpd.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"

    print(f"Cephalon UI — interface disponible sur {url}")
    print(f"  Source de données : {output_dir.resolve()}")
    print("  Pressez Ctrl+C pour arrêter le serveur.")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt de Cephalon UI.")
    finally:
        httpd.server_close()
        print("Serveur arrêté.")


def main(argv: list[str] | None = None) -> int:
    """Entry point console ``cephalon-ui`` (autonome, pour l'exe PyInstaller)."""
    import argparse
    parser = argparse.ArgumentParser(
        prog="cephalon-ui",
        description="Interface web pour parcourir le lore Warframe récupéré.",
    )
    parser.add_argument("--out", type=Path, default=None,
                        help="Dossier des megafiles (défaut: ./out)")
    parser.add_argument("--port", type=int, default=0,
                        help="Port à utiliser (0 = libre, défaut)")
    parser.add_argument("--no-browser", action="store_true",
                        help="N'ouvre pas le navigateur automatiquement.")
    args = parser.parse_args(argv)

    output_dir = args.out or _default_output_dir()
    if not output_dir.is_dir():
        print(f"Attention : aucun dossier de données trouvé ({output_dir}).")
        print("Lancez d'abord `cephalon run` pour générer les megafiles.")
    serve_forever(output_dir, port=args.port,
                  open_browser=not args.no_browser)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())