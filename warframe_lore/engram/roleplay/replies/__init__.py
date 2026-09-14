"""Deterministic and one-shot replies of the Roleplay terminal.

Facade: the speaker-identity and guild-member answers (built from accredited
data, never from the model) and the one-shot member-card comment.  Callers import
from here, whatever the internal split is.
"""

from __future__ import annotations

from .comment import member_comment
from .identity import (
    external_organic_reply,
    identity_reply,
    member_comment_request,
    member_roster_reply,
)

__all__ = ["external_organic_reply", "identity_reply", "member_comment",
           "member_comment_request", "member_roster_reply"]
