"""Declaration of the ``cephalon`` subcommands, grouped by domain.

Façade : :func:`register_all` branche les trois groupes sur le sous-parseur
racine — ``pipeline`` (run/diff/status/recent/buckets/init-db), ``tools``
(ui/export-entities/kim-dm) et ``bot`` (bot run/version/help).  Ajouter une
commande = une entrée dans le groupe concerné.
"""

from __future__ import annotations

import argparse

from . import bot, pipeline, tools

# Group order = declaration order in ``cephalon --help``.
GROUPS = (pipeline, tools, bot)


def register_all(sub: argparse._SubParsersAction) -> None:
    """Declare every ``cephalon`` subcommand on ``sub``."""
    for group in GROUPS:
        group.register(sub)


__all__ = ["GROUPS", "register_all"]
