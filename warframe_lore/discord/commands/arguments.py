"""Argument parsing shared by the ``!`` commands.

Single responsibility: turn a raw command argument into a validated value — an
on/off switch or a word of an enumerated vocabulary — with ONE wording for the
usage reminders and the privilege refusal.  Pure module: no Discord, no I/O.
"""

from __future__ import annotations

TRUE_WORDS = frozenset({"on", "oui", "1", "true", "actif", "enable", "enabled"})
FALSE_WORDS = frozenset({"off", "non", "0", "false", "inactif", "disable",
                         "disabled"})
DENIED = ("Ces réglages relèvent de mon Concepteur et du Haut Commandement, "
          "organique.")


def as_switch(argument: str) -> bool | None:
    """Parse an on/off argument (``None`` when it is not a switch value)."""
    word = (argument or "").strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    return None


def on_off(flag: bool) -> str:
    """French rendering of a switch (one wording for every confirmation)."""
    return "activé" if flag else "désactivé"


def usage(prefix: str, command: str, choices: str) -> str:
    """Usage reminder of one command (``Usage : !lang fr | en``)."""
    return f"Usage : {prefix}{command} {choices}"


__all__ = ["DENIED", "FALSE_WORDS", "TRUE_WORDS", "as_switch", "on_off",
           "usage"]
