"""Bot reactions to attacks (probes, insults, spam) and to answer feedback."""

from __future__ import annotations

from .feedback import REACTION_DOWN, REACTION_UP, FeedbackMixin
from .hostile import HostileMixin
from .insults import HOSTILE_AFTER_INSULTS, InsultMixin
from .spam import SpamMixin

__all__ = ["HOSTILE_AFTER_INSULTS", "REACTION_DOWN", "REACTION_UP",
           "FeedbackMixin", "HostileMixin", "InsultMixin", "SpamMixin"]
