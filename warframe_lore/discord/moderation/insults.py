"""Detection of second-person insolence aimed at the bot (FR + EN).

When a NON-Creator organic insults the bot, the bot answers by itself: cold,
classy, escalating (see :mod:`comebacks`) so the insulter is filed as a
"specimen" instead of gaining ground.  Creator insults are NEVER intercepted
here — they fall through to the free-chat persona; that decision belongs to the
router (the authenticated ``creator`` boolean), not to this module.

Pure module: no discord.py dependency.  The curated vocabulary avoids firing on
lore ("merde" alone, third-person "nul", untargeted insults are excluded).
"""

from __future__ import annotations

import re

from .comebacks import COMEBACKS, comeback_for

_INSOLENCE_PATTERNS = (
    # Gross directives (an order is an insult).
    re.compile(r"\bavale( et dis merci)?\b", re.IGNORECASE),
    re.compile(r"\b(ferme[- ]?la?|ta gueule|tais[- ]toi|la ferme|ta bouche)\b",
               re.IGNORECASE),
    re.compile(r"\bva (te faire (foutre|voir|cuire|coucher)|te cacher)\b",
               re.IGNORECASE),
    re.compile(r"\b(casse[- ]toi|d[ée]gage|fous le camp|d[ée]merde[- ]toi|"
               r"d[ée]brouille[- ]toi)\b", re.IGNORECASE),
    # "You are …" — direct judgements about the Cephalon.
    re.compile(r"t[' ]es (une? )?(nul(le)?|c[oô]n(ne)?|idiot(e)?|d[ée]bile|"
               r"merde|rat[ée]|pitoyable)\b", re.IGNORECASE),
    re.compile(r"\btu (es|serais|restes) (une? )?(nul(le)?|c[oô]n(ne)?|"
               r"idiot(e)?|d[ée]bile|merde|rat[ée]|pitoyable|bon(ne)? à "
               r"rien)\b", re.IGNORECASE),
    re.compile(r"\btu (ne sers?( à)? |ne serviras( à)? |es bon(ne)? à )?"
               r"rien\b", re.IGNORECASE),
    re.compile(r"\btu (nous)? fais chier\b|\btu (nous )?(saoules|so[ûu]les)\b",
               re.IGNORECASE),
    # Exclamations / reproaches.
    re.compile(r"\btu (me |nous )?(fais|fait) chier\b|"
               r"\b(fais|fait)(-moi| moi)? chier\b|"
               r"\b(fais|fait) chi[éée]\b", re.IGNORECASE),
    re.compile(r"\bt[' ]es (chiant|chiante)\b|"
               r"\btu (me )?(saoules?|so[ûu]les?)\b", re.IGNORECASE),
    # Direct vulgar repertoire.
    re.compile(r"esp[èe]ce de (c[oô]n|connard|cr[eé]tin|d[ée]bile|abruti|"
               r"imb[cé]cile|idiot|rat[ée])\b", re.IGNORECASE),
    re.compile(r"\b(connard|connasse|encul[ée]|trou[ -]du[ -]cul|branleur|"
               r"abruti|gros(se)? c[oô]n(ne)?|pauvre (c[oô]n|type|merde)|"
               r"grosse merde|rabat[- ]joie)\b", re.IGNORECASE),
    re.compile(r"sale (bot|machine|algo|robot|cephalon|tas de ferraille|"
               r"merde)\b", re.IGNORECASE),
    # English equivalents.
    re.compile(r"\b(shut up|shut the (fuck |hell )?up|stfu)\b", re.IGNORECASE),
    re.compile(r"\b(fuck you|screw you|piss off|get lost|buzz off|"
               r"fuck off)\b", re.IGNORECASE),
    re.compile(r"\byou (suck|stink|blow)\b", re.IGNORECASE),
    re.compile(r"\byou[’' ]re (a )?(useless|pathetic|lame|dumb|stupid|"
               r"a joke|trash)\b", re.IGNORECASE),
    re.compile(r"\b(moron|dumbass|jackass)\b", re.IGNORECASE),
)


def detect_insult(text: str) -> bool:
    """True if the message is a second-person insult aimed at the bot."""
    return any(p.search(text or "") for p in _INSOLENCE_PATTERNS)


__all__ = ["COMEBACKS", "comeback_for", "detect_insult"]
