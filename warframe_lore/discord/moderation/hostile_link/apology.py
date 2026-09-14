"""Apology detection (deterministic) for the hostile-session redemption.

The hostile persona NEVER returns to normal without an explicit apology signal,
and a sarcastic apology (laughter, irony, cheeky dismissal) must NOT trigger the
redemption: the Cephalon keeps demanding a genuine one.  Pure string matching —
no LLM, no discord.py.
"""

from __future__ import annotations

# Apology markers (case-insensitive): French first, then English equivalents.
APOLOGY_MARKERS = (
    "pardon", "excuse", "excusez-moi", "désolé", "desole", "désoléé",
    "sorry", "mea culpa", "j'ai eu tort", "j'avais tort", "j'admets ma faute",
    "je m'excuse", "je suis navré", "je suis navree",
    "navré", "navree", "regret",
    "i apologize", "i apologise", "my apologies", "forgive me",
    "i am sorry", "i'm sorry", "im sorry", "i was wrong", "it was my fault",
    "my fault", "i behaved badly", "i am ashamed",
)

# Sarcastic overtones: apology markers may be faked (mockery, irony, laughter).
SARCASTIC_MARKERS = (
    # Mockery / laughter
    "mdr", "lol", "haha", "héhé", "hehe", "hihi", "rires", "je rigole",
    "j'rigole", "joke", "kidding", "just kidding", "😏", "😈", "🙄", "😂",
    "🤣", "😜", "🤪", "ironie", "ironique", "sarcasme", "sarcastique",
    # Dismissive / cheeky "apologies"
    "pardon rien du tout", "excusez-moi rien du tout",
    "désolé si c'est trop", "sorry not sorry",
    "désolé de t'avoir blessé, créature", "navré, vraiment",
)


def is_apology(text: str) -> bool:
    """True if the message is (probably) an apology to the bot."""
    low = (text or "").lower()
    return any(marker in low for marker in APOLOGY_MARKERS)


def is_sincere_apology(text: str) -> bool:
    """True only for a NON-sarcastic apology (real redemption)."""
    if not is_apology(text):
        return False
    low = (text or "").lower()
    return not any(marker in low for marker in SARCASTIC_MARKERS)


__all__ = ["APOLOGY_MARKERS", "SARCASTIC_MARKERS", "is_apology",
           "is_sincere_apology"]
