"""Point d'entrée ``python -m warframe_lore`` (rétro-compatible).

Délégue à l'interface en ligne de commande ``cephalon`` (voir ``cli.py``).
Sans argument, ``python -m warframe_lore`` équivaut à ``cephalon run`` —
le pipeline complet en mode delta incrémental (comportement historique).
"""

from __future__ import annotations

import sys

from .cli import main


def _argv_with_default_run(argv: list[str]) -> list[str]:
    """Injecte la sous-commande ``run`` quand aucun argument n'est passé."""
    if not argv:
        return ["run"]
    return argv


if __name__ == "__main__":
    raise SystemExit(main(_argv_with_default_run(sys.argv[1:])))
