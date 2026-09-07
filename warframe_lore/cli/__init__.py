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

Organisation : ``support`` (logging/config/UI), ``commands`` (implémentation
des sous-commandes), ``parser`` (argparse + normalisation legacy).
"""

from __future__ import annotations

import sys

from .parser import build_parser, normalize_legacy_argv
from .support import setup_logging


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(normalize_legacy_argv(argv))

    setup_logging(args.verbose)

    if args.command is None or args.command == "help" or args.func is None:
        parser.print_help()
        return 0

    return args.func(args)


__all__ = ["main"]