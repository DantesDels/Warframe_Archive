"""Support for the ``cephalon`` CLI: logging, config, UI launcher.

Shared constants and cross-cutting helpers (config building, bucket
display, free-port detection, web UI launch in a detached process).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from ..api import BucketConfig
from ..config import PROJECT_ROOT, load_config

log = logging.getLogger("cephalon")

PROJECT_DEFAULT_DB_INIT_SQL = PROJECT_ROOT / "init_db.sql"
VERSION = "1.0.0"
DEFAULT_UI_PORT = 49772


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def build_config(args) -> tuple:
    """Build the config + bucket config shared by the commands."""
    config = load_config()
    if getattr(args, "database_url", None):
        config.database_url = args.database_url

    project_default = PROJECT_ROOT / "buckets.json"
    bucket_path = getattr(args, "bucket_config", None) or (
        project_default if project_default.exists() else None)
    if bucket_path is not None:
        bucket_config = BucketConfig.from_file(bucket_path)
    else:
        bucket_config = BucketConfig()
    return config, bucket_config


def print_buckets(bucket_config: BucketConfig) -> None:
    for spec in bucket_config.specs:
        print(f"[{spec.id}]")
        print(f"  title      : {spec.title}")
        print(f"  file       : {spec.filename}")
        print(f"  categories : {', '.join(spec.categories) or '-'}")
        print(f"  include titles: {', '.join(spec.title_include) or '-'}")
        print(f"  exclude titles: {', '.join(spec.title_exclude) or '-'}")
        print()


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


# ---------------------------------------------------------- timeline build
# La Timeline (``/timeline/`` dans l'UI) est une app Vue/ELK servie depuis
# ``ui/static/timeline``. Elle est construite depuis le vault Obsidian :
#   1. ``scripts/extractor.js`` (Node) lit ``data/vault/`` et écrit
#      ``data/timeline/graph.json`` (racine du projet) ;
#   2. Vite compile l'app vers ``ui/static/timeline/`` (graph.json inclus).
TIMELINE_DIR = PROJECT_ROOT / "warframe_lore" / "ui" / "timeline"
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _print_safe(text: str) -> None:
    """Affiche ``text`` sans planter sur les consoles non-UTF-8 (cp1252)."""
    try:
        encoding = sys.stdout.encoding or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(encoding, "replace"))
        sys.stdout.buffer.flush()
    except (AttributeError, UnicodeEncodeError):
        print(text, flush=True)


def _timeline_step(step: str, *cmd: str) -> bool:
    """Exécute une étape de la construction Timeline et affiche sa sortie."""
    _print_safe(f"Timeline: {step} ...")
    try:
        proc = subprocess.run(
            [str(a) for a in cmd],
            cwd=str(TIMELINE_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        print(f"Timeline: {step} impossible à lancer ({exc}).",
              file=sys.stderr)
        return False
    out = (_ANSI_RE.sub("", proc.stdout or "")).strip()
    if out:
        _print_safe(out)
    if proc.returncode != 0:
        print(f"Timeline: {step} a échoué (exit {proc.returncode}).",
              file=sys.stderr)
        return False
    print(f"Timeline: {step} terminé.")
    return True


def build_timeline() -> bool:
    """Génère la Timeline (extraction Obsidian + build Vue/Vite).

    Intégrée à ``cephalon run`` : le résultat est servi automatiquement par
    l'interface sur ``/timeline/``. Retourne False (sans lever) si Node, le
    dossier ou npm install font défaut — ``run`` continue quand même.
    """
    node = shutil.which("node")
    if node is None:
        print("Timeline: Node.js introuvable — construction ignorée.",
              file=sys.stderr)
        return False
    if not TIMELINE_DIR.is_dir():
        print(f"Timeline: dossier introuvable ({TIMELINE_DIR}) — "
              "construction ignorée.", file=sys.stderr)
        return False
    vite_bin = TIMELINE_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite_bin.is_file():
        print("Timeline: Vite non installé (npm install) — construction "
              "ignorée.", file=sys.stderr)
        return False

    ok = _timeline_step("extraction Obsidian", node, "scripts/extractor.js")
    if ok:
        ok = _timeline_step("build Vite", node, vite_bin, "build")
    if ok:
        print("Timeline prête — servie sur /timeline/ de l'interface.")
    return ok


def launch_ui(config) -> None:
    """Launch the web UI in the background and open the browser.

    The server runs in a detached process (dedicated console on Windows) and
    points the browser at the chosen port; ``cephalon run`` does not wait.
    """
    out = config.output_dir
    port = DEFAULT_UI_PORT if port_free(DEFAULT_UI_PORT) else 0
    cmd = [sys.executable, "-m", "warframe_lore.ui.server",
           "--out", str(out), "--port", str(port)]
    flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    try:
        subprocess.Popen(
            cmd,
            cwd=os.getcwd(),
            creationflags=flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        print(f"Could not launch the web UI: {exc}", file=sys.stderr)
        return
    if port:
        print(f"Web UI launched: http://127.0.0.1:{port}/")
    else:
        print("Web UI launched (automatic free port).")