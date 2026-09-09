"""Query expansion by alias (nicknames -> canonical names).

Some entries are only known to the embedding model under their canonical
name (e.g. "Lettie" -> wiki page "Leticia"). ``resolve_alias`` enriches
the query to embed (reminder), provides an alias note injected into the
prompt (the model can translate the nickname) and a canonical name for
disambiguation when no exact data is retrieved.
"""

from __future__ import annotations

# nickname (lowercase) -> (canonical name, mnemonic note for the prompt).
ALIASES = {
    "lettie": ("Leticia",
               "Lettie = Leticia Garcia, membre des Hex (1999)"),
}


def resolve_alias(question: str) -> tuple[str, str, str]:
    """Returns (enriched question, alias note, canonical name).

    Without a match, the question is returned as-is and the other two
    values are empty.
    """
    low = question.lower()
    for alias, (canon, note) in ALIASES.items():
        if alias in low:
            # Lexical expansion forces the embedding to target chunks of the
            # canonical name, where the nickname alone would be ambiguous.
            return f"{question} ({canon})", note, canon
    return question, "", ""