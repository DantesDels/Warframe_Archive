"""Legacy root-flag compatibility for the ``cephalon`` CLI.

Single responsibility: convert the old syntax (``python -m warframe_lore --force
--skip-sql``) into the modern subcommand form, so existing scripts and habits keep
working.  Pure argv rewriting — no argparse, no side effect.
"""

from __future__ import annotations

# Modern subcommands: when argv starts with one of them, nothing is rewritten.
KNOWN_COMMANDS = {"run", "diff", "status", "recent", "buckets", "init-db",
                  "ui", "export-entities", "kim-dm", "bot", "version", "help"}

VERBOSE_FLAGS = ("--verbose", "-v")
PIPELINE_FLAGS = ("--force", "--skip-sql")
BOT_FLAGS = ("-bot", "--bot")

# Legacy root flag -> modern subcommand (first match wins).
LEGACY_SUBCOMMANDS = (
    ("--init-db", ("init-db",)),
    ("--list-buckets", ("buckets",)),
    ("--init-bucket-config", ("buckets", "--init")),
)


def normalize_legacy_argv(argv: list[str]) -> list[str]:
    """Convert the old syntax (root flags) into subcommands.

    Backwards compatibility: ``python -m warframe_lore --force --skip-sql``
    becomes ``cephalon run --force --skip-sql``; ``--init-db``,
    ``--list-buckets`` and ``--init-bucket-config`` are translated to the
    matching subcommands.
    """
    if not argv:
        return argv
    if argv[0] in BOT_FLAGS:
        return ["bot", *argv[1:]]
    if argv[0] in KNOWN_COMMANDS or argv[0] in ("-h", "--help"):
        return argv

    verbose = any(flag in argv for flag in VERBOSE_FLAGS)
    clean = [token for token in argv if token not in VERBOSE_FLAGS]
    normalized = _legacy_subcommand(clean)
    database_url = _option_value(clean, "--database-url")
    if database_url:
        normalized += ["--database-url", database_url]
    if verbose:
        normalized.insert(0, "--verbose")
    return normalized


def _legacy_subcommand(clean: list[str]) -> list[str]:
    """Modern subcommand matching the legacy root flags (``run`` by default)."""
    for flag, replacement in LEGACY_SUBCOMMANDS:
        if flag in clean:
            return list(replacement)
    normalized = ["run"]
    for flag in PIPELINE_FLAGS:
        if flag in clean:
            normalized.append(flag)
    bucket_path = _option_value(clean, "--bucket-config")
    if bucket_path:
        normalized += ["--bucket-config", bucket_path]
    return normalized


def _option_value(clean: list[str], option: str) -> str | None:
    """Value following ``option`` in the cleaned argv, or ``None``."""
    for index, token in enumerate(clean):
        if token == option and index + 1 < len(clean):
            return clean[index + 1]
    return None


__all__ = ["KNOWN_COMMANDS", "normalize_legacy_argv"]
