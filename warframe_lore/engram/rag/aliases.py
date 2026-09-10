"""Query expansion by alias (nicknames -> canonical names).

Some entries are only known to the embedding model under their canonical
name (e.g. "Lettie" -> wiki page "Leticia", or French nicknames like
"le Mercenaire d'Os" -> Ordan Karris / Ordis). :class:`AliasResolver`
enriches the query to embed (reminder), provides an alias note injected
into the prompt (the model can translate the nickname) and a canonical
name for disambiguation when no exact data is retrieved.

The expansion is a MIDDLEWARE step applied to the raw user query BEFORE
vectorization (``RAGService.retrieve``) — the enriched text is the one
embedded, so the alias actually reaches ``pgvector``.
"""

from __future__ import annotations

# nickname (lowercase) -> (canonical name, mnemonic note for the prompt).
# Extensible at runtime via :meth:`AliasResolver.register`.
ALIASES = {
    "lettie": ("Leticia",
               "Lettie = Leticia Garcia, membre des Hex (1999)"),
    "mercenaire d'os": (
        "Ordan Karris Ordis",
        "« Mercenaire d'Os » = Ordan Karris, l'humain devenu le Cephalon "
        "Ordis"),
}


class AliasResolver:
    """Declarative, extensible alias registry (alias -> canonical + note)."""

    def __init__(self, aliases: dict[str, tuple[str, str]] | None = None
                 ) -> None:
        self._aliases = dict(aliases or ALIASES)

    def register(self, alias: str, canonical_name: str, note: str) -> None:
        """Adds a nickname mapping at runtime (name -> canonical -> note)."""
        self._aliases[alias.lower()] = (canonical_name, note)

    def resolve(self, question: str) -> tuple[str, str, str]:
        """Returns (enriched question, alias note, canonical name).

        Without a match, the question is returned as-is and the other two
        values are empty.
        """
        low = question.lower()
        for alias, (canon, note) in self._aliases.items():
            if alias in low:
                # Lexical expansion forces the embedding to target chunks of
                # the canonical name, where the nickname alone would be
                # ambiguous.
                return f"{question} ({canon})", note, canon
        return question, "", ""


# Default registry (module-level `resolve_alias` kept as a thin wrapper for
# backward compatibility); services may inject their own resolver instead.
_DEFAULT_RESOLVER = AliasResolver()


def resolve_alias(question: str) -> tuple[str, str, str]:
    """Resolves a question against the default alias registry."""
    return _DEFAULT_RESOLVER.resolve(question)


__all__ = ["ALIASES", "AliasResolver", "resolve_alias"]