"""Interface en ligne de commande ``cephalon`` — gestion du pipeline.

Commandes disponibles (préfixe ``cephalon``) :
    * ``cephalon run``      : exécute le pipeline complet (delta incrémental,
                              conserve l'existant, n'insère que le nouveau)
                              puis lance l'interface web locale (navigateur).
    * ``cephalon diff``     : prévisualise les pages à mettre à jour, sans
                              rien écrire (dry-run).
    * ``cephalon status``   : état courant (pages, chunks, canon, dernière sync).
    * ``cephalon recent``   : dernières pages modifiées / insérées.
    * ``cephalon buckets``  : liste les buckets (avec ``--init`` pour les
                              matérialiser dans ``buckets.json``).
    * ``cephalon init-db``  : crée le schéma PostgreSQL (``init_db.sql``).
    * ``cephalon ui``       : lance l'interface web locale (navigateur).
    * ``cephalon export-entities`` : synchronise les entités du jeu.
    * ``cephalon kim-dm``      : télécharge le miroir KIM (datamine).
    * ``cephalon-ui``       : entry point autonome de l'interface (exe).
    * ``cephalon version``  : affiche la version du paquet.
    * ``cephalon help``     : aide générale.

Rétro-compatibilité : ``python -m warframe_lore [--force|--skip-sql|--init-db|...]``
fonctionne toujours ; sans sous-commande il équivaut à ``cephalon run``.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import subprocess
import sys
from pathlib import Path

from .api import BucketConfig
from .config import PROJECT_ROOT, load_config
from .db import SQLDatabaseManager
from .scraper import Scraper

log = logging.getLogger("cephalon")

PROJECT_DEFAULT_DB_INIT_SQL = PROJECT_ROOT / "init_db.sql"
VERSION = "1.0.0"
DEFAULT_UI_PORT = 49772

# --------------------------------------------------------------------- setup
def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def _build_config(args) -> tuple:
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


def _print_buckets(bucket_config: BucketConfig) -> None:
    for spec in bucket_config.specs:
        print(f"[{spec.id}]")
        print(f"  titre       : {spec.title}")
        print(f"  fichier     : {spec.filename}")
        print(f"  catégories  : {', '.join(spec.categories) or '-'}")
        print(f"  inclu titres: {', '.join(spec.title_include) or '-'}")
        print(f"  exclu titres: {', '.join(spec.title_exclude) or '-'}")
        print()


# ------------------------------------------------------------- command: run
async def _cmd_init_database_impl(database_url: str) -> None:
    manager = SQLDatabaseManager(database_url)
    await manager.connect()
    try:
        await manager.run_ddl_script(PROJECT_DEFAULT_DB_INIT_SQL)
    finally:
        await manager.close()
    print(f"Base initialisée depuis {PROJECT_DEFAULT_DB_INIT_SQL.name}.")


def _cmd_init_database(args) -> int:
    config, _ = _build_config(args)
    asyncio.run(_cmd_init_database_impl(config.database_url))
    return 0


def _cmd_run(args) -> int:
    config, bucket_config = _build_config(args)
    scraper = Scraper(
        config=config,
        bucket_config=bucket_config,
        database_url=None if args.skip_sql else config.database_url,
    )
    try:
        scraper.run(force=args.force)
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130
    print("Synchronisation terminée avec succès.")
    if not getattr(args, "no_ui", False):
        _launch_ui(config)
    return 0


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _launch_ui(config) -> None:
    """Lance l'interface web en arrière-plan et ouvre le navigateur.

    Le serveur tourne dans un process détaché (console dédiée sur Windows) et
    presse le navigateur sur le port choisi ; ``cephalon run`` n'attend pas.
    """
    out = config.output_dir
    port = DEFAULT_UI_PORT if _port_free(DEFAULT_UI_PORT) else 0
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


async def _cmd_diff_impl(args) -> dict:
    config, bucket_config = _build_config(args)
    scraper = Scraper(
        config=config,
        bucket_config=bucket_config,
        database_url=None if args.skip_sql else config.database_url,
    )
    if scraper.db is not None:
        await scraper.db.connect()
    try:
        return await scraper.delta_plan(force=args.force)
    finally:
        if scraper.db is not None:
            await scraper.db.close()


def _cmd_diff(args) -> int:
    plan = asyncio.run(_cmd_diff_impl(args))
    total = sum(len(t) for t in plan.values())
    if total == 0:
        print("Aucune mise à jour à faire — contenu déjà à jour.")
        return 0
    print(f"Delta : {total} page(s) à mettre à jour (force={args.force}):")
    for bucket_id, titles in sorted(plan.items()):
        print(f"\n[{bucket_id}]  ({len(titles)} page(s))")
        for title in sorted(titles):
            print(f"    • {title}")
    return 0


async def _cmd_status_impl(args) -> None:
    config, _ = _build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    try:
        stats = await manager.db_stats()
    finally:
        await manager.close()

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"

    print("État de la base de lore :")
    print(f"  Pages en base            : {stats['total_pages']}")
    print(f"  Chunks (RAG)             : {stats['total_chunks']}")
    print(f"  Dialogues KIM            : {stats['total_kim_dialogues']}")
    print(f"  Enregistrements de sync  : {stats['total_sync_records']}")
    print(f"  Dernière page créée      : {_fmt(stats['last_page_created_at'])}")
    print(f"  Dernière page mise à jour: {_fmt(stats['last_page_updated_at'])}")
    print(f"  Dernière synchronisation : {_fmt(stats['last_sync_at'])}")

    if stats["total_by_canon"]:
        print("\n  Par statut canon :")
        for status, count in sorted(stats["total_by_canon"].items()):
            print(f"    {status:<18} {count}")
    if stats["pages_by_bucket"]:
        print("\n  Pages par bucket :")
        for name, count in sorted(stats["pages_by_bucket"].items()):
            print(f"    {name:<32} {count}")


def _cmd_status(args) -> int:
    asyncio.run(_cmd_status_impl(args))
    return 0


async def _cmd_recent_impl(args) -> None:
    config, _ = _build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    try:
        rows = await manager.recent_pages(limit=args.limit)
    finally:
        await manager.close()

    def _fmt(dt) -> str:
        return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "—"

    if not rows:
        print("Aucune page enregistrée.")
        return
    print(f"Dernières {len(rows)} page(s) modifiées :")
    for i, row in enumerate(rows, start=1):
        print(f"  {i:>2}. {row['page_title']:<50} "
              f"[{row['canon_status']:<16}] "
              f"créé {_fmt(row['created_at'])} / maj {_fmt(row['updated_at'])}")


def _cmd_recent(args) -> int:
    asyncio.run(_cmd_recent_impl(args))
    return 0


async def _cmd_export_entities_impl(args) -> None:
    from .export import EXPORT_CATEGORIES, PublicExportClient

    config, _ = _build_config(args)
    manager = SQLDatabaseManager(config.database_url)
    await manager.connect()
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    client = PublicExportClient(
        cache_dir=args.cache_dir or Path("cache") / "public_export",
        langs=langs)
    try:
        if args.categories:
            wanted = {k: v for k, v in EXPORT_CATEGORIES.items()
                      if k in args.categories}
            client.categories = wanted
        stats = await client.sync(manager, langs=langs, force=args.force)
    finally:
        await manager.close()
    print(f"Public Export : {stats['entities']} entités écrites, "
          f"{stats['assets']} actifs traités, {stats['skipped']} en échec.")


def _cmd_export_entities(args) -> int:
    asyncio.run(_cmd_export_entities_impl(args))
    return 0


def _cmd_buckets(args) -> int:
    _, bucket_config = _build_config(args)
    if args.init:
        target = args.bucket_config or (PROJECT_ROOT / "buckets.json")
        BucketConfig.write_defaults(target)
        print(f"Config buckets par défaut écrite -> {target}")
        return 0
    _print_buckets(bucket_config)
    return 0


def _cmd_version(args) -> int:
    print(f"cephalon (warframe-archives) — {VERSION}")
    print(f"paquet : {Path(__file__).resolve().parent}")
    return 0


def _cmd_ui(args) -> int:
    """Lance l'interface web locale (voir ``warframe_lore.ui.server``)."""
    from .ui.server import serve_forever

    config, _ = _build_config(args)
    serve_forever(output_dir=args.out or config.output_dir,
                  port=args.port,
                  open_browser=not args.no_browser)
    return 0


# --------------------------------------------------------- command: kim-dm
def _cmd_kim_dm(args) -> int:
    from .kim_dm import mirror_kim_dm

    config, _ = _build_config(args)
    output_dir = args.out or config.output_dir
    langs = tuple(args.lang) if args.lang else ("en", "fr")
    downloaded, failed = mirror_kim_dm(output_dir, langs=langs, force=args.force)
    if downloaded:
        print(f"Téléchargés dans {output_dir / 'kim_dm'} : {', '.join(downloaded)}")
    else:
        print("Rien à télécharger (cache déjà à jour — utilisez --force).")
    if failed:
        print("Échecs :")
        for err in failed:
            print(f"  • {err}")
        return 1
    return 0


# ------------------------------------------------------------------ assembly
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cephalon",
        description="Scrape & clean Warframe lore (quêtes, dialogues, KIM, "
                    "factions) depuis l'API MediaWiki officielle vers des "
                    "megafiles JSON + PostgreSQL (RAG-ready).",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging.")
    sub = parser.add_subparsers(dest="command", metavar="COMMANDE")

    # --- run
    p_run = sub.add_parser("run", help="Exécute le pipeline complet "
                                       "(delta incrémental).")
    p_run.add_argument("--force", action="store_true",
                       help="Re-traiter toutes les pages (ignore le delta).")
    p_run.add_argument("--skip-sql", action="store_true",
                       help="Pipeline JSON seul (sans PostgreSQL).")
    p_run.add_argument("--no-ui", action="store_true",
                       help="N'ouvre pas l'interface web à la fin de la sync.")
    p_run.add_argument("--bucket-config", type=Path, default=None)
    p_run.add_argument("--database-url", type=str, default=None)
    p_run.set_defaults(func=_cmd_run)

    # --- diff
    p_diff = sub.add_parser("diff", help="Prévisualise le delta sans écrire.")
    p_diff.add_argument("--force", action="store_true",
                        help="Considère TOUTES les pages comme à re-traiter.")
    p_diff.add_argument("--skip-sql", action="store_true",
                        help="Simule en mode JSON seul (tout est à re-traiter).")
    p_diff.add_argument("--bucket-config", type=Path, default=None)
    p_diff.add_argument("--database-url", type=str, default=None)
    p_diff.set_defaults(func=_cmd_diff)

    # --- status
    p_status = sub.add_parser("status", help="État courant de la base.")
    p_status.add_argument("--database-url", type=str, default=None)
    p_status.set_defaults(func=_cmd_status)

    # --- recent
    p_recent = sub.add_parser("recent", help="Dernières pages modifiées.")
    p_recent.add_argument("--limit", type=int, default=10,
                          help="Nombre de pages à afficher (défaut 10).")
    p_recent.add_argument("--database-url", type=str, default=None)
    p_recent.set_defaults(func=_cmd_recent)

    # --- buckets
    p_buckets = sub.add_parser("buckets", help="Liste les buckets.")
    p_buckets.add_argument("--init", action="store_true",
                           help="Écrit la config par défaut dans buckets.json.")
    p_buckets.add_argument("--bucket-config", type=Path, default=None)
    p_buckets.set_defaults(func=_cmd_buckets)

    # --- init-db
    p_init = sub.add_parser("init-db", help="Crée le schéma PostgreSQL.")
    p_init.add_argument("--database-url", type=str, default=None)
    p_init.add_argument("--bucket-config", type=Path, default=None)
    p_init.set_defaults(func=_cmd_init_database)

    # --- ui
    p_ui = sub.add_parser("ui", help="Lance l'interface web locale.")
    p_ui.add_argument("--port", type=int, default=0,
                      help="Port à utiliser (0 = port libre automatique).")
    p_ui.add_argument("--no-browser", action="store_true",
                      help="N'ouvre pas le navigateur automatiquement.")
    p_ui.add_argument("--out", type=Path, default=None,
                      help="Dossier des megafiles (défaut: out/).")
    p_ui.set_defaults(func=_cmd_ui)

    # --- export-entities
    p_export = sub.add_parser(
        "export-entities",
        help="Synchronise les entités du jeu (Public Export) vers la base.")
    p_export.add_argument("--lang", action="append", choices=sorted(_SUPPORTED_LANGS),
                          help="Langues à traiter (défaut: en fr).")
    p_export.add_argument("--categories", action="append",
                          help="Catégories d'actifs (défaut: les 10 utilitaires).")
    p_export.add_argument("--cache-dir", type=Path, default=None,
                          help="Dossier de cache des actifs (défaut: "
                               "cache/public_export/).")
    p_export.add_argument("--force", action="store_true",
                          help="Re-télécharge les actifs (ignore le cache).")
    p_export.add_argument("--database-url", type=str, default=None)
    p_export.set_defaults(func=_cmd_export_entities)

    # --- kim-dm
    p_kim_dm = sub.add_parser(
        "kim-dm",
        help="Télécharge/cache le miroir KIM (graphes de dialogue du jeu + "
             "dictionnaires de localisation) dans out/kim_dm/.")
    p_kim_dm.add_argument("--out", type=Path, default=None,
                          help="Dossier des megafiles (défaut: out/).")
    p_kim_dm.add_argument("--lang", action="append", choices=sorted(_SUPPORTED_LANGS),
                          help="Langues du dictionnaire à télécharger "
                               "(défaut: en fr).")
    p_kim_dm.add_argument("--force", action="store_true",
                          help="Re-télécharge tout (ignore le cache local).")
    p_kim_dm.set_defaults(func=_cmd_kim_dm)

    # --- version
    p_version = sub.add_parser("version", help="Affiche la version.")
    p_version.set_defaults(func=_cmd_version)

    # --- help
    p_help = sub.add_parser("help", help="Affiche l'aide générale.")
    p_help.set_defaults(func=None)

    return parser


_KNOWN_COMMANDS = {"run", "diff", "status", "recent", "buckets",
                   "init-db", "ui", "export-entities", "kim-dm",
                   "version", "help"}

_SUPPORTED_LANGS = {"de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                    "ru", "tc", "th", "tr", "uk", "zh"}


def _normalize_legacy_argv(argv: list[str]) -> list[str]:
    """Convertit l'ancienne syntaxe (flags racines) en sous-commandes.

    Rétro-compatibilité : ``python -m warframe_lore --force --skip-sql``
    devient ``cephalon run --force --skip-sql`` ; ``--init-db``,
    ``--list-buckets`` et ``--init-bucket-config`` sont traduits vers les
    sous-commandes correspondantes.
    """
    if not argv:
        return argv
    first = argv[0]
    if first in _KNOWN_COMMANDS or first in ("-h", "--help"):
        return argv

    verbose = "--verbose" in argv or "-v" in argv
    clean = [t for t in argv if t not in ("--verbose", "-v")]

    def opt_value(opt: str) -> str | None:
        for i, token in enumerate(clean):
            if token == opt and i + 1 < len(clean):
                return clean[i + 1]
        return None

    if "--init-db" in clean:
        normalized = ["init-db"]
    elif "--list-buckets" in clean:
        normalized = ["buckets"]
    elif "--init-bucket-config" in clean:
        normalized = ["buckets", "--init"]
    else:
        normalized = ["run"]
        for flag in ("--force", "--skip-sql"):
            if flag in clean:
                normalized.append(flag)
        bucket_path = opt_value("--bucket-config")
        if bucket_path:
            normalized += ["--bucket-config", bucket_path]

    database_url = opt_value("--database-url")
    if database_url:
        normalized += ["--database-url", database_url]
    if verbose:
        normalized.insert(0, "--verbose")
    return normalized


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = _build_parser()
    args = parser.parse_args(_normalize_legacy_argv(argv))

    _setup_logging(args.verbose)

    if args.command is None or args.command == "help" or args.func is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())