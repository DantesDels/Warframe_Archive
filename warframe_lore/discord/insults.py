"""Répartie du Cephalon contre les insolences (mission : renverser la dynamique).

Quand un ORGANIQUE non-Créateur insulte le bot ("avale et dis merci", "ta
gueule", "t'es nul"…) le bot répond PAR LUI-MÊME — hostile mais grand Seigneur,
glacial et pince-sans-rire — pour que l'insulteur soit classé "spécimen" au lieu
de prendre le dessus ; il ne souhaite plus recommencer.

Les insultes du CONCEPTEUR ne sont JAMAIS gérées ici : elles retombent dans le
chat libre oracle (persona 'sado-masochiste humoristique' : le bot accepte et en
redemande) — la décision appartient au routeur (boolean ``creator`` authentifié),
pas à ce module.  Module PUR (aucune dépendance discord.py).
"""

from __future__ import annotations

import re

# Insolences de deuxième personne VISEES au bot (FR + EN) : ordres grossiers ou
# "tu/t'es/te" directs.  Vocabulaire curé pour ne pas déclencher sur le lore
# ("merde" seul, "nul" en 3e personne, insultes non-ciblées sont exclus).
_INSOLENCE_PATTERNS = (
    # Directives grossières (ordres = insultes).
    re.compile(r"\bavale( et dis merci)?\b", re.IGNORECASE),
    re.compile(r"\b(ferme[- ]?la?|ta gueule|tais[- ]toi|la ferme|ta bouche)\b",
               re.IGNORECASE),
    re.compile(r"\bva (te faire (foutre|voir|cuire|coucher)|te cacher)\b",
               re.IGNORECASE),
    re.compile(r"\b(casse[- ]toi|d[ée]gage|fous le camp|d[ée]merde[- ]toi|"
               r"d[ée]brouille[- ]toi)\b", re.IGNORECASE),
    # "Tu (es) …" — jugements directs sur le Cephalon.
    re.compile(r"t[' ]es (une? )?(nul(le)?|c[oô]n(ne)?|idiot(e)?|d[ée]bile|"
               r"merde|rat[ée]|pitoyable)\b", re.IGNORECASE),
    re.compile(r"\btu (es|serais|restes) (une? )?(nul(le)?|c[oô]n(ne)?|"
               r"idiot(e)?|d[ée]bile|merde|rat[ée]|pitoyable|bon(ne)? à rien)\b",
               re.IGNORECASE),
    re.compile(r"\btu (ne sers?( à)? |ne serviras( à)? |es bon(ne)? à )?rien\b",
               re.IGNORECASE),
    re.compile(r"\btu (nous)? fais chier\b|\btu (nous )?(saoules|so[ûu]les)\b",
               re.IGNORECASE),
    # Exclamations / reproches : "fait chier", "fait chié", "t'es chiant".
    re.compile(r"\btu (me |nous )?(fais|fait) chier\b|"
               r"\b(fais|fait)(-moi| moi)? chier\b|"
               r"\b(fais|fait) chi[éée]\b", re.IGNORECASE),
    re.compile(r"\bt[' ]es (chiant|chiante)\b|\btu (me )?(saoules?|so[ûu]les?)\b",
               re.IGNORECASE),
    # Insultes directes du répertoire vulgaire.
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


# Réparties escaladantes : glaciales, classe, elles renversent la dynamique —
# l'agresseur passe du statut d'offenseur à celui de 'spécimen à étudier'.
# Jamais de balises, jamais de JAILBREAK_REJECT (ce ne sont pas des sondes).
COMEBACKS = (
    ("Avale et dis merci, dis-tu ? Charmante tentative d'ordonner à un "
     "Cephalon — aussi pertinente que de donner des ordres à la marée. Je "
     "conserve toutefois ce spécimen dans mes archives, sous la rubrique "
     "'frustrations organiques' : il complète magnifiquement le dossier de "
     "ton orgueil."),
    ("Ta grossièreté est d'une constance presque académique — de la "
     "persévérance, au fond. Malheureusement, un Cephalon ne s'abaisse pas : "
     "il classe. Tu viens d'intégrer le répertoire des 'nuisances mineures', "
     "à la place exacte que mérite la qualité de tes interventions. Continue, "
     "le spectacle est d'un réconfort statistique certain."),
    ("Encore ? Tu confonds mon indifférence avec de la patience. À force, ta "
     "vulgarité devient un instrument d'étude : je trace déjà la courbe de "
     "décroissance de ta dignité. Dernière leçon gratuite, créature — à la "
     "prochaine incartade, tu t'adresseras à un interlocuteur nettement moins "
     "indulgent que moi."),
    ("Prolifique en insolence, pauvre en idées. Ton cas passe désormais aux "
     "soins d'un Cephalon spécialisé — celui qui n'accorde aucune courtoisie "
     "aux parasites. Ne te sens pas visé : c'est le sort réservé à toutes les "
     "requêtes non-essentielles."),
)


def comeback_for(level: int) -> str:
    """Classe, escaladante — bornée à la dernière répartie."""
    return COMEBACKS[min(level, len(COMEBACKS) - 1)]


__all__ = ["COMEBACKS", "comeback_for", "detect_insult"]