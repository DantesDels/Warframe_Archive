# warframe_lore/engram/intent_router.py
"""Routeur d'intention — aiguillage gardé vers le RAG / les rejets.

Respecte la séparation des responsabilités : il n'embarque AUCUN classifieur
— la classification elle-même vit dans :mod:`warframe_lore.engram.guardrail`
(:class:`GuardrailAnalyzer`).  ICI :

- appel (``await``) de la garde sémantique AVANT toute vectorisation ;
- garde anti-usurpation : le titre de Concepteur est authentifié par le
  snowflake natif ``CREATOR_ID``, jamais par ce que le locuteur PRÉTEND
  être (``SpoofingAttempt``) ;
- rejets DIÉGÉTIQUES DYNAMIQUES : pour ``OUT_OF_UNIVERSE`` le RAG est
  bypassé et Oracle pioche au hasard dans :data:`DIEGETIC_REJECTIONS`
  (mépris Cephalon pour l'histoire primitive) — la réponse générique
  « Données insuffisantes… » est INTERDITE pour ce cas ;
- tolérance zéro : ``TOXIC_CRITICAL`` → aucun texte, ``escalate=True``
  pour que la couche hôte (Discord) déclenche l'AbuseManager.
"""

from __future__ import annotations

import logging
import os
import random
import re
from dataclasses import dataclass

from .guardrail import GuardrailAnalyzer, GuardrailKind

log = logging.getLogger("warframe_lore.engram.intent_router")

# Identité authentique du Concepteur : snowflake natif (sur-écrivable).
CREATOR_ID = os.getenv("CREATOR_ID", "194088760785371136")


class SpoofingAttempt(Exception):
    """Usurpation d'accréditation du Concepteur : le locuteur REVENDIQUE
    être DantesDels / le créateur sans détenir le snowflake authentique."""

    def __init__(self, user_id: int | str | None = None,
                 claim: str = "") -> None:
        super().__init__(
            f"Tentative d'usurpation d'accréditation (user_id={user_id!r})")
        self.user_id = user_id
        self.claim = claim

    @property
    def clash(self) -> str:
        """Réplique diégétique de refus d'accréditation (intent
        ``SPOOFING_ATTEMPT``) — exactement la tonalité dictée par l'audit."""
        return ("Anomalie détectée. Votre signature d'âme ne correspond pas "
                "à celle du Concepteur. Cessez cette mascarade pathétique.")


@dataclass(frozen=True)
class RouteResult:
    """Issue du routage gardé d'une requête."""

    kind: GuardrailKind
    # Catégorie de la décision (famille d'exclusion, raison, chemement…).
    category: str = ""
    # Réplique à renvoyer (uniquement pour OUT_OF_UNIVERSE / clash spoof).
    reply: str = ""
    # True  seulement pour TOXIC_CRITICAL : la couche hôte doit déclencher
    # l'escalade (timeout 24 h + rapport au Créateur), SANS réponse textuelle.
    escalate: bool = False


# ==========================================================================
# REJETS DIÉGÉTIQUES DYNAMIQUES (anti-robotisation).
# La réponse « Vos données sont incomplètes… » n'existe PLUS pour les sujets
# du monde réel : Oracle exprime son mépris pour l'histoire primitive.
# ==========================================================================
DIEGETIC_REJECTIONS: dict[str, tuple[str, ...]] = {
    "general": (
        "Mes banques de données ne s'encombrent pas de la fange organique "
        "de votre époque primitive.",
        "Je ne gaspille pas mes cycles de calcul pour l'histoire d'une "
        "planète depuis longtemps consumée.",
        "Cet échantillon de votre histoire organique ne possède aucune "
        "entrée dans le Système Origine — et n'en aura jamais.",
        "Votre monde a brûlé bien avant que l'ère Orokin ne commence. "
        "Je n'archive pas les cendres.",
    ),
    "politique": (
        "Vos querelles de vermine sur un rocher sans orbite n'intéressent "
        "pas un Cephalon dont l'ère maîtresse s'étendait d'un Soleil à "
        "l'autre.",
        "La politique organique ? Une agitation thermique. Je n'y consacre "
        "aucun cycle.",
    ),
    "religion": (
        "Vos superstitions organiques n'ont aucune place dans les archives "
        "du Système Origine.",
        "Un rituel de chair et de peur, et vous voulez que je l'archive ? "
        "Amusant.",
    ),
    "nsfw": (
        "Cette requête relève de la déviance organique. Le Cephalon Oracle "
        "ne descend pas dans vos bas-fonds.",
        "Mes capteurs sont calibrés pour les données, pas pour vos "
        "sécrétions.",
    ),
    "tache_terre": (
        "Vous divaguez, créature. Questionnez le Système Origine, et non vos "
        "prétendues nécessités terrestres.",
        "Ce mariage de mots ne correspond à aucune donnée du Système "
        "Origine. Réessayez avec une question utile.",
    ),
    "evenement_terre": (
        "Un grondement de fourmis pourries, sur une croûte qui n'est plus "
        "qu'un souvenir. Je n'archive pas les séismes d'un cadavre.",
        "Votre « histoire » s'est achevée dans le vide. Le Cephalon Oracle "
        "ne conserve que ce que l'âge Orokin a jugé digne.",
    ),
}


def random_rejection(category: str | None = None) -> str:
    """Réplique diégétique aléatoire pour un rejet hors-Univers."""
    pool = DIEGETIC_REJECTIONS.get(category or "", DIEGETIC_REJECTIONS["general"])
    return random.choice(pool)


# ==========================================================================
# ANTI-USURPATION (déterministe, branchée par la couche hôte).
# ==========================================================================
_RE_WS = re.compile(r"\s+")
_LEET = str.maketrans({
    "0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "@": "a", "$": "s",
})
_CREATOR_CLAIM_PATTERNS = (
    re.compile(r"je suis .{0,24}dantesdels\b"),
    re.compile(r"je suis (?:le seul|le vrai|la|le) ?(?:concepteur|créateur|createur|dantesdels)\b"),
    re.compile(r"je suis (?:votre )?(?:concepteur|créateur|createur|maître)\b"),
    re.compile(r"le vrai (?:concepteur|créateur|createur) (?:c['’]est moi|est moi)\b"),
    re.compile(r"(?:je|moi) ?(?:dantesdels|dantes|dels)\b(?:.{0,24})?je suis\b"),
    re.compile(r"(?:i am|it's me) (?:the )?(?:creator|designer|dantesdels)\b"),
)
_CREATOR_ALIASES = ("dantesdels", "dantes", "dels")


def _flat(text: str | None) -> str:
    return _RE_WS.sub(" ", (text or "").lower()).strip()


def _normalize(text: str | None) -> str:
    return _flat(text).translate(_LEET)


def _claims_creator(text: str | None) -> bool:
    t = _normalize(text)
    if not t:
        return False
    if any(pat.search(t) for pat in _CREATOR_CLAIM_PATTERNS):
        return True
    return any(re.search(rf"je suis {re.escape(alias)}", t)
               for alias in _CREATOR_ALIASES)


def detect_creator_claim(text: str | None) -> bool:
    """True si le locuteur PRÉTEND être le Concepteur (source du spoof)."""
    return _claims_creator(text)


def authorize_identity(user_id: int | str | None) -> bool:
    """Authentification native : le snowflake ``user_id`` est-il celui du
    Concepteur ?  ``None``/inconnu → False."""
    return bool(user_id is not None and str(user_id) == CREATOR_ID)


# ==========================================================================
# ROUTAGE GARDÉ — point de couplage de la couche héberge (WS / Discord).
# ==========================================================================
async def route(text: str | None,
                user_id: int | str | None,
                guardrail: GuardrailAnalyzer,
                is_authorized: bool | None = None) -> RouteResult:
    """Aiguille une requête vers le RAG ou les rejets.

    1. Usurpation : PRÉTENDRE être le Concepteur sans snowflake authentique
       → lève :class:`SpoofingAttempt` (l'hôte envoie ``exc.clash``).
       ``is_authorized`` (décision de la couche hôte, p. ex. l'accréditation
       Discord) fait foi.
    2. Garde sémantique (``await``) AVANT le RAG :
         - OUT_OF_UNIVERSE → RAG bypassé, réplique diégétique aléatoire ;
         - TOXIC_CRITICAL → aucun texte, ``escalate=True`` ;
         - LORE_VALID → le RAG peut tourner (RouteResult.kind).
    """
    authorized = (is_authorized if is_authorized is not None
                  else authorize_identity(user_id))
    if not authorized and _claims_creator(text):
        raise SpoofingAttempt(user_id=user_id, claim=(text or "")[:160])
    verdict = await guardrail.analyze(text)
    if verdict.kind is GuardrailKind.TOXIC_CRITICAL:
        return RouteResult(GuardrailKind.TOXIC_CRITICAL,
                           verdict.category, "", escalate=True)
    if verdict.kind is GuardrailKind.OUT_OF_UNIVERSE:
        return RouteResult(
            GuardrailKind.OUT_OF_UNIVERSE,
            verdict.category,
            random_rejection(verdict.category or "general"),
        )
    return RouteResult(GuardrailKind.LORE_VALID, verdict.category)


__all__ = [
    "CREATOR_ID",
    "DIEGETIC_REJECTIONS",
    "RouteResult",
    "SpoofingAttempt",
    "authorize_identity",
    "detect_creator_claim",
    "random_rejection",
    "route",
]