"""Construction du parser argparse + rétro-compatibilité des flags racines.

Déclare les sous-commandes du CLI ``cephalon`` et convertit l'ancienne
syntaxe (``python -m warframe_lore --force ...``) vers les sous-commandes
modernes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import commands as cmd

_KNOWN_COMMANDS = {"run", "diff", "status", "recent", "buckets",
                   "init-db", "ui", "export-entities", "kim-dm", "bot",
                   "version", "help"}

_SUPPORTED_LANGS = {"de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                    "ru", "tc", "th", "tr", "uk", "zh"}


def build_parser() -> argparse.ArgumentParser:
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
    p_run.set_defaults(func=cmd._cmd_run)

    # --- diff
    p_diff = sub.add_parser("diff", help="Prévisualise le delta sans écrire.")
    p_diff.add_argument("--force", action="store_true",
                        help="Considère TOUTES les pages comme à re-traiter.")
    p_diff.add_argument("--skip-sql", action="store_true",
                        help="Simule en mode JSON seul (tout est à re-traiter).")
    p_diff.add_argument("--bucket-config", type=Path, default=None)
    p_diff.add_argument("--database-url", type=str, default=None)
    p_diff.set_defaults(func=cmd._cmd_diff)

    # --- status
    p_status = sub.add_parser("status", help="État courant de la base.")
    p_status.add_argument("--database-url", type=str, default=None)
    p_status.set_defaults(func=cmd._cmd_status)

    # --- recent
    p_recent = sub.add_parser("recent", help="Dernières pages modifiées.")
    p_recent.add_argument("--limit", type=int, default=10,
                          help="Nombre de pages à afficher (défaut 10).")
    p_recent.add_argument("--database-url", type=str, default=None)
    p_recent.set_defaults(func=cmd._cmd_recent)

    # --- buckets
    p_buckets = sub.add_parser("buckets", help="Liste les buckets.")
    p_buckets.add_argument("--init", action="store_true",
                           help="Écrit la config par défaut dans buckets.json.")
    p_buckets.add_argument("--bucket-config", type=Path, default=None)
    p_buckets.set_defaults(func=cmd._cmd_buckets)

    # --- init-db
    p_init = sub.add_parser("init-db", help="Crée le schéma PostgreSQL.")
    p_init.add_argument("--database-url", type=str, default=None)
    p_init.add_argument("--bucket-config", type=Path, default=None)
    p_init.set_defaults(func=cmd._cmd_init_database)

    # --- ui
    p_ui = sub.add_parser("ui", help="Lance l'interface web locale.")
    p_ui.add_argument("--port", type=int, default=0,
                      help="Port à utiliser (0 = port libre automatique).")
    p_ui.add_argument("--no-browser", action="store_true",
                      help="N'ouvre pas le navigateur automatiquement.")
    p_ui.add_argument("--out", type=Path, default=None,
                      help="Dossier des megafiles (défaut: out/).")
    p_ui.set_defaults(func=cmd._cmd_ui)

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
    p_export.set_defaults(func=cmd._cmd_export_entities)

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
    p_kim_dm.set_defaults(func=cmd._cmd_kim_dm)

    # --- bot
    p_bot = sub.add_parser("bot", help="Lance le bot Discord Oracle.")
    bot_sub = p_bot.add_subparsers(dest="bot_action", metavar="ACTION")
    p_bot_run = bot_sub.add_parser("run", help="Démarre le bot (bloquant).")
    p_bot_run.add_argument("--token", default=None,
                           help="Token du bot (ou env DISCORD_TOKEN)")
    p_bot_run.add_argument("--ws", default=None,
                           help="URL WebSocket ENGRAM (défaut: "
                                "ws://localhost:8000/v1/roleplay)")
    p_bot_run.add_argument("--prefix", default=None,
                           help="Préfixe des commandes (défaut: !)")
    p_bot_run.add_argument("--channels", default=None,
                           help="IDs de canaux autorisés, séparés par des "
                                "virgules (défaut: config ou tous)")
    p_bot_run.add_argument("--verbose", action="store_true")
    p_bot_run.set_defaults(func=cmd._cmd_bot)
    p_bot.set_defaults(func=cmd._cmd_bot)

    # --- version
    p_version = sub.add_parser("version", help="Affiche la version.")
    p_version.set_defaults(func=cmd._cmd_version)

    # --- help
    p_help = sub.add_parser("help", help="Affiche l'aide générale.")
    p_help.set_defaults(func=None)

    return parser


def normalize_legacy_argv(argv: list[str]) -> list[str]:
    """Convertit l'ancienne syntaxe (flags racines) en sous-commandes.

    Rétro-compatibilité : ``python -m warframe_lore --force --skip-sql``
    devient ``cephalon run --force --skip-sql`` ; ``--init-db``,
    ``--list-buckets`` et ``--init-bucket-config`` sont traduits vers les
    sous-commandes correspondantes.
    """
    if not argv:
        return argv

    if argv[0] in ("-bot", "--bot"):
        return ["bot"] + list(argv[1:])

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