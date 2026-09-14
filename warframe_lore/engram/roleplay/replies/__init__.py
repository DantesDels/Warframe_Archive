"""Deterministic and one-shot replies of the Roleplay terminal.

Facade: the speaker-identity answer (:mod:`identity`), the guild-member answers
(:mod:`member`) and the one-shot member-card comment (:mod:`comment`) — all built
from accredited data, never guessed by the model.
"""

from __future__ import annotations

from .comment import member_comment, member_comment_request
from .identity import identity_reply
from .member import external_organic_reply, member_roster_reply

__all__ = ["external_organic_reply", "identity_reply", "member_comment",
           "member_comment_request", "member_roster_reply"]
