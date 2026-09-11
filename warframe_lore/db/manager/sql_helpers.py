"""Pure SQL helpers (no state) shared by the manager mixins.

These functions stay at module level so they are testable and reusable
(wiki timestamp parsing, canon status normalization, splitting a
multi-command SQL script).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ...output.models import CanonStatus


def parse_timestamp(value: str | None) -> Optional[datetime]:
    """Converts an ISO timestamp into a datetime (None if invalid).

    The ``touched`` field of the wiki API has the form
    ``2026-09-05T16:20:11Z`` (Z suffix = UTC).
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def as_canon_status_string(canon_status: CanonStatus | str) -> str:
    """Normalizes a canon status to its string value."""
    if isinstance(canon_status, CanonStatus):
        return canon_status.value
    return canon_status


def split_sql_statements(sql_script: str) -> list[str]:
    """Splits a SQL script into individual statements.

    asyncpg forbids multiple commands in a prepared statement: the script
    is split on semicolons outside string literals, ignoring ``-- ...``
    comments (which may contain apostrophes).
    """
    statements: list[str] = []
    current_statement: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    line_length = len(sql_script)

    while index < line_length:
        character = sql_script[index]
        next_character = sql_script[index + 1] if index + 1 < line_length else ""

        # SQL '--' comment outside a string: skip until the end of line.
        if character == "-" and next_character == "-" \
                and not in_single_quote and not in_double_quote:
            while index < line_length and sql_script[index] != "\n":
                index += 1
            continue

        if character == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
        elif character == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
        current_statement.append(character)
        if character == ";" and not in_single_quote and not in_double_quote:
            statement_text = "".join(current_statement).strip()
            if statement_text:
                statements.append(statement_text)
            current_statement = []
        index += 1

    trailing_statement = "".join(current_statement).strip()
    if trailing_statement:
        statements.append(trailing_statement)
    return statements