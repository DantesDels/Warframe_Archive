"""Support pour le CLI ``cephalon`` : logging, config, lancement UI.

Constantes partagées et helpers transverses (construction de la config,
affichage des buckets, détection de port libre, ouverture de l'interface
web dans un process détaché).
"""

from __future__ import annotations

import logging
import os
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
    """Construit la config + la config buckets partagées par les commandes."""
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
        print(f"  titre       : {spec.title}")
        print(f"  fichier     : {spec.filename}")
        print(f"  catégories  : {', '.join(spec.categories) or '-'}")
        print(f"  inclu titres: {', '.join(spec.title_include) or '-'}")
        print(f"  exclu titres: {', '.join(spec.title_exclude) or '-'}")
        print()


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def launch_ui(config) -> None:
    """Lance l'interface web en arrière-plan et ouvre le navigateur.

    Le serveur tourne dans un process détaché (console dédiée sur Windows) et
    presse le navigateur sur le port choisi ; ``cephalon run`` n'attend pas.
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
        print(f"Impossible de lancer l'interface web : {exc}", file=sys.stderr)
        return
    if port:
        print(f"Interface web lancée : http://127.0.0.1:{port}/")
    else:
        print("Interface web lancée (port libre automatique).")