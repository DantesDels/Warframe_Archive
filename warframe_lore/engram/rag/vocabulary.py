"""Archive-wide vocabulary: does a word exist anywhere in the corpus?

The post-generation gate (:mod:`.verify`) grounds an answer on the RETRIEVED
passages only.  Those are a narrow slice: a faithful Codex sheet legitimately
names in-universe common nouns and real entities archived on OTHER pages
("l'Empire", "le Conclave", "Entrati"), which the local gate flags as
confabulation and replaces with the abstention chain.  This component answers
the wider question — the word occurs in at least one archived chunk — so the
gate can excuse it, while a name absent from EVERY page stays rejected.  The
probe covers every spelling of the same lexeme (``lexeme_forms`` in
:mod:`.verify`): an archive that knows "distant" also knows the sheet's
feminine "Distante".
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from ...db import LoreChunk
from .verify import lexeme_forms

# One candidate row is enough to prove presence.
_ROW_LIMIT = 1
# Per-process memo: a page's vocabulary is stable between ingestions.
_CACHE_MAX = 4096


class ArchiveVocabulary:
    """Presence of a word (any inflection) in ``lore_chunks`` (memoized)."""

    def __init__(self, sessions: async_sessionmaker,
                 cache_max: int = _CACHE_MAX) -> None:
        self.sessions = sessions
        self.cache_max = cache_max
        self._cache: dict[str, bool] = {}

    async def unknown(self, words: set[str]) -> set[str]:
        """Subset of ``words`` absent from EVERY archived passage."""
        return {word for word in words if not await self._present(word)}

    async def _present(self, word: str) -> bool:
        if word in self._cache:
            return self._cache[word]
        # Word-boundary regex, case-insensitive: a substring match would
        # ground an invented name inside an unrelated longer word.  Every
        # spelling of the same lexeme is probed at once (one round trip):
        # the archive that knows "distant" also contains "Distante".
        variants = "|".join(re.escape(form) for form in lexeme_forms(word))
        pattern = rf"\y(?:{variants})\y"
        async with self.sessions() as session:
            statement = (
                select(LoreChunk.id)
                .where(LoreChunk.content_markdown.op("~*")(pattern))
                .limit(_ROW_LIMIT)
            )
            found = (await session.execute(statement)).first() is not None
        if len(self._cache) < self.cache_max:
            self._cache[word] = found
        return found


__all__ = ["ArchiveVocabulary"]
