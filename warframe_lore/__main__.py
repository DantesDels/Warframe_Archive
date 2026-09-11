"""Entry point for ``python -m warframe_lore`` (backward-compatible).

Delegates to the ``cephalon`` CLI (see ``cli.py``).
Without arguments, ``python -m warframe_lore`` is equivalent to ``cephalon run``
— the full pipeline in incremental delta mode (legacy behaviour).
"""

from __future__ import annotations

import sys

from .cli import main


def _argv_with_default_run(argv: list[str]) -> list[str]:
    """Inject the ``run`` sub-command when no arguments are provided."""
    if not argv:
        return ["run"]
    return argv


if __name__ == "__main__":
    raise SystemExit(main(_argv_with_default_run(sys.argv[1:])))
