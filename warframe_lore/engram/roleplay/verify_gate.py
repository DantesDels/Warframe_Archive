"""Post-generation gate: verify a RAG reply, then close the narrative part.

Deterministic post-processing of a BUFFERED reply (a RAG turn never
live-streams): the archives (:class:`ArchiveVocabulary`) validate the answer,
a confabulation is replaced by the fixed error, and the mandate closing line
of a part is imposed — ``story_more`` decides WHICH sentence (invitation
while fragments remain, archivist stop once drained).  The reply reaches the
wire only AFTER this gate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..rag import CONFABULATION_ERROR, RAG_ERROR, verify_answer_with_archive
from .prompt import STORY_LENS_STARTS
from .purge import canonical_story_closing, purge_story_closing

if TYPE_CHECKING:
    from ..rag import ArchiveVocabulary


async def verified_response(
    response: str,
    rag_context: str,
    *,
    vocabulary: ArchiveVocabulary | None,
    user_name: str | None,
    user_role: str | None,
    targeted_era: str | None,
    leverian_warframe: str | None,
    story_lens: str | None,
    story: bool,
    story_more: bool,
) -> str:
    """Gate the buffered reply: verify against the archives, then close.

    An empty reply is the abstention (``RAG_ERROR``); a confabulated reply is
    swapped for ``CONFABULATION_ERROR``; a faithful reply is purged of any
    stacked closing and receives the canonical closing line of the part.
    """
    if not response:
        return RAG_ERROR
    lens_open = (STORY_LENS_STARTS.get(story_lens or "")
                 if story and not targeted_era else "")
    allowed = " ".join(filter(None, (
        user_name, user_role, targeted_era, leverian_warframe, lens_open,
    )))
    ok, _ = await verify_answer_with_archive(
        response, rag_context, vocabulary, extra_allowed=allowed)
    if not ok:
        return CONFABULATION_ERROR
    # One trailing closing line, no padded tail: the token the client
    # renders must hold the canonical end too.
    response = purge_story_closing(response)
    if story:
        # ``story_more`` decides WHICH sentence closes the part (invitation
        # while fragments remain, archivist stop once drained): the model's
        # missing, wrong or stacked tail is replaced deterministically.
        response = canonical_story_closing(response, more=story_more)
    return response


__all__ = ["verified_response"]
