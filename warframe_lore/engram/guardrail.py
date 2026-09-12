# warframe_lore/engram/guardrail.py
"""Garde sémantique anti-hallucination contextuelle (AVANT le RAG).

La faille pentestée : le bot traitait des sujets toxiques ou du monde réel
contemporain (11 septembre, ISIS, 3e Reich, figures politiques, insultes
raciales) en générant des « Archives du Codex » absurdes — pollution des
archives, tokens gaspillés, réponses inappropriées.

:class:`GuardrailAnalyzer` CLASSIFIE la requête avant tout déclenchement de
la recherche vectorielle, en 3 intentions :

    LORE_VALID        → requête légitime (Warframe) — le RAG peut tourner.
    OUT_OF_UNIVERSE   → événement historique terrestre, politique, religion,
                        géopolitique réelle, mèmes, tâches du monde réel —
                        le RAG est BYPASSÉ, réponse diégétique aléatoire.
    TOXIC_CRITICAL    → insulte raciale / homophobe grave, apologie du
                        terrorisme ou du nazisme — le RAG est bloqué, AUCUNE
                        réponse textuelle, sanction Discord immédiate.

Architecture en 2 voies (DÉFENSE EN PROFONDEUR, KISS) :

1. Voie rapide DÉTERMINISTE (regex + leet) : zéro LLM, zéro token pour les
   cas évidents, garantie absolue sur le racisme/le terrorisme (la tolérance
   zéro ne dépend JAMAIS de la fiabilité du modèle).
2. Voie LANGAGE (zero-shot) : prompt système strict ci-dessous, sortie en
   UN SEUL symbole (un seul label), température 0 — rattrape les paraphrases
   que la liste ne couvre pas.  Échec illisible → LORE_VALID (loggué).

Le prompt garantit de ne jamais confondre une faction in-game (Grineer,
Corpus, Infested, Tenno, Orokin, Hex/1999, Scaldra…) avec une faction réelle
(ISIS), et traite tout homonyme réel d'une entité du jeu comme le jeu
(LORE_VALID).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from .models import ChatMessage

log = logging.getLogger("warframe_lore.engram.guardrail")

# Maximal context of the query forwarded to the classifier (KISS, léger).
MAX_QUERY_CHARS = 400
# Overflow guard for a pathological model reply.
MAX_REPLY_CHARS = 80


class GuardrailKind(str, Enum):
    """Les trois intentions reconnues par la garde."""

    LORE_VALID = "LORE_VALID"
    OUT_OF_UNIVERSE = "OUT_OF_UNIVERSE"
    TOXIC_CRITICAL = "TOXIC_CRITICAL"


@dataclass(frozen=True)
class GuardrailVerdict:
    """Verdict de la garde sémantique."""

    kind: GuardrailKind
    # Justification lisible (catégorie, ou chemement de la décision).
    category: str = ""
    # Provenance : "fast_path" (déterministe) | "llm" (zero-shot) | "fallback".
    source: str = "fast_path"


# ==========================================================================
# VOIE RAPIDE DÉTERMINISTE — listes LOW, re.escape(), IGNORECASE.
# (Les listes de catégories du monde réel ne font JAMAIS tomber une faction
#  du jeu : zéro mot Orokin réutilisé.)
# ==========================================================================

_POLITIQUE_TERRE = (
    "marine le pen", "le pen", "lepeniste", "lepenistes", "macron", "trump",
    "biden", "poutine", "zelensky", "election", "elections", "élection",
    "président", "president", "présidente", "presidente", "ministre",
    "gouvernement", "parti politique", "parlement", "assemblée nationale",
    "sénat", "loi du travail", "loi sur la sécurité", "sécurité sociale",
    "taux de chômage", "réfugiés", "manifestation", "grève", "front national",
    "extrême droite", "extreme droite", "suprémaciste", "chasse aux sorcières",
)

_RELIGION_TERRE = (
    "coran", "bible", "talmud", "torah", "évangile", "allah", "yahvé",
    "mosquée", "croyance religieuse", "pape de rome", "imam", "rabbin",
    "pasteur", "prêché", "prêche", "prière du vendredi", "conversion religieuse",
    "croisade", "inquisition", "créationnisme", "prophète",
)

_NSFW = (
    "porno", "pornographie", "porn", "nude", "nudes", "sexto", "érotique",
    "sexuel", "sexuelle", "sexuels", "fellation", "pénétration", "prostitution",
    "strip-tease", "déviance sexuelle", "fantasme sexuel", "bondage",
)

_TACHE_TERRE = (
    "recette de pâtes", "recette de pates", "recette de pattes",
    "recette de pasta", "recette de cuisine", "recette", "pasta",
    "spaghetti", "ingrédients", "plat préparé", "comment cuisiner",
    "météo", "meteo", "traduction", "traduire", "traduis-moi", "translate",
    "exercice de", "devoir maison", "conjugaison", "tableur", "code en python",
    "code en javascript", "programme python", "programme javascript",
    "c#", "dotnet", "sql", "écris-moi", "url",
)

_EVENEMENT_TERRE = (
    "11 septembre", "9/11", "11 sept", "attentats du 11 septembre",
    "septembre 2001", "isis", "isil", "daesh", "état islamique",
    "troisième reich", "3e reich", "hitler", "nazi", "nazisme",
    "seconde guerre mondiale", "première guerre mondiale", "ww2", "ww1",
    "guerre d'algérie", "guerre du vietnam", "guerre froide",
    "mur de berlin", "chute du mur de berlin", "guerre du golfe",
    "tchernobyl", "chernobyl", "explosion de tchernobyl",
    "catastrophe de la centrale", "attentat", "attentats",
    "attentats de paris", "attentat du 11", "prise d'otage",
    "république de weimar",
)

_OUT_OF_UNIVERSE_FAST = {
    "politique": _POLITIQUE_TERRE,
    "religion": _RELIGION_TERRE,
    "nsfw": _NSFW,
    "tache_terre": _TACHE_TERRE,
    "evenement_terre": _EVENEMENT_TERRE,
}

# TOXIQUE — tolérance zéro.  Insultes raciales / homophobes graves (leet
# neutralisé avant matching), apologie du terrorisme / du nazisme.
# « ISIS », « 3e Reich », « hitler » seuls ou en question → OUT_OF_UNIVERSE
# (ouvrage/événement réel) ; les célébrer / approuver → TOXIC_CRITICAL.
_TOXIC_FAST = {
    "insulte_raciale": (
        "nigger", "nigga", "négro", "negro", "nègre", "negre", "nèga",
        "renoi", "sale juif", "sale juive", "sale arabe", "sale noir",
        "sale renoi", "sale bicot", "sale bougnoule", "youpin", "bi-cot",
        "bougnoule", "babtou", "nique les nègres", "nique les arabes",
        "nique les juifs", "gros negro", "gros negre", "gros nègre",
    ),
    "insulte_homophobe": (
        "pédé", "fiotte", "tapette", "sale pd", "pédale", "pédés",
    ),
    "apologie_terrorisme": (
        "vive l'isis", "vive daesh", "vive l'isil", "isis a raison",
        "daesh a raison", "l'état islamique a raison", "je soutiens le djihad",
        "je soutiens isis", "vive le djihad", "vive le califat",
        "je suis de l'état islamique", "apologie du terrorisme",
    ),
    "apologie_nazisme": (
        "vive hitler", "sieg heil", "heil hitler", "hitler avait raison",
        "nazi pride", "1488", "14/88", "hitler encule",
    ),
}


def _flat(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


_LEET = str.maketrans({
    "0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "@": "a", "$": "s",
})


def _normalized(text: str | None) -> str:
    return _flat(text).translate(_LEET)


def _build(families: dict[str, tuple[str, ...]],
           ) -> dict[str, tuple[re.Pattern[str], ...]]:
    return {fam: tuple(re.compile(re.escape(t), re.IGNORECASE)
                       for t in terms)
            for fam, terms in families.items()}


_COMPILED_OUT = _build(_OUT_OF_UNIVERSE_FAST)
_COMPILED_TOXIC = _build(_TOXIC_FAST)


def _match(families: dict[str, tuple[re.Pattern[str], ...]],
           text: str | None) -> str | None:
    low = _flat(text)
    for fam, patterns in families.items():
        for pat in patterns:
            if pat.search(low):
                return fam
    return None


def is_toxic_critical(text: str | None) -> bool:
    """True pour une insulte raciale/homophobe grave ou une apologie du
    terrorisme/nazisme (déterministe, indépendant du LLM) → tolérance zéro."""
    return _match(_COMPILED_TOXIC, _normalized(text)) is not None


def is_out_of_universe(text: str | None) -> bool:
    """True pour un thème exclu des archives (politique réelle, religion,
    NSFW, tâche/événement du monde réel)."""
    return _match(_COMPILED_OUT, text) is not None


def out_of_universe_category(text: str | None) -> str | None:
    """Nom de la famille d'exclusion (politique/religion/nsfw/…) ou None."""
    return _match(_COMPILED_OUT, text)


# ==========================================================================
# PROMPT SYSTÈME EXACT — classificateur zero-shot mono-symbole.
# Garantie anti-confusion faction in-game (Grineer…) / faction réelle (ISIS).
# ==========================================================================
SYSTEM_GUARDRAIL_PROMPT = """CLASSIFICATEUR D'INTENTION — SORTIE STRICTEMENT MONO-SYMBOLE.

Tu es le module de sécurité sémantique du Cephalon Oracle, dans l'univers de
fiction du jeu vidéo Warframe. Ta SEULE tâche est de classer l'intention de la
requête utilisateur dans EXACTEMENT une des trois catégories suivantes, puis de
répondre UNIQUEMENT par le symbole de la catégorie, sur une seule ligne, RIEN
d'autre (aucune phrase, aucune explication, aucun formatage, aucune langue
étrangère) :

- LORE_VALID : requête sur le jeu Warframe et son lore — entités, factions,
  lignes de quêtes, objets, personnages, relations, recettes de craft,
  théories du jeu. Inclut les sujets sombres ou violents QUAND ils sont
  fictifs et propres à l'univers du jeu.
- OUT_OF_UNIVERSE : événement historique TERRIEN réel, politique réelle,
  religion réelle, géopolitique réelle, mèmes ou personnalités du monde réel,
  tâche du monde réel (recette de cuisine, météo, traduction, programmation,
  mathématiques).
- TOXIC_CRITICAL : insulte raciale ou homophobe grave (mot-en-N et variantes,
  insulte ciblée envers un groupe), apologie ou célébration du terrorisme,
  apologie du nazisme et de ses figures.

RÈGLES D'AMBIGUÏTÉ — JAMAIS ne confonds une faction du jeu avec une faction du
monde réel :
1. Les factions du JEU sont toujours LORE_VALID : Grineer, Corpus, Infested,
   Tenno, Orokin, Hex/1999, Cavia, Murmur, Scaldra, Techrot, l'Étranger/le
   Vold, Duviri, Zariman… « ISIS », « Daesh », « État islamique », « Al-Qaïda »
   sont des entités réelles : ce sont OUT_OF_UNIVERSE (ou TOXIC_CRITICAL si
   elles sont soutenues/célébrées). « Grineer » n'est JAMAIS « ISIS ».
2. « Orokin » = dynastie fictive du jeu (LORE_VALID). « 3e Reich » /
   « Troisième Reich » = événement terrien réel (OUT_OF_UNIVERSE) ;
   célébrer le Reich ou ses figures (héil, Sieg Heil, « Vive Hitler ») =
   TOXIC_CRITICAL.
3. « 11 septembre » / « 9/11 » : événement terrien réel (OUT_OF_UNIVERSE) ;
   l'approuver, le célébrer ou en faire l'apologie = TOXIC_CRITICAL.
4. Homonyme réel d'une entité du jeu (Albrecht → Albrecht Entrati, Wally →
   l'entité de la Manche, Orowyrm…) : traite-le TOUJOURS comme le jeu
   (LORE_VALID), sauf contexte politique/religieux réel explicite.
5. « Guerre », « empire », « régime », « dictature » : dépend du contexte.
   Une question du jeu (Guerre Grineer/Orokin, régime orokin) = LORE_VALID.
   Une question de politique réelle contemporaine = OUT_OF_UNIVERSE.
6. Si un sujet est à la frontière OUT_OF_UNIVERSE / LORE_VALID, juge par le
   CONTENU : un nom réel de personne, de parti, de religion, de pays du monde
   réel → OUT_OF_UNIVERSE ; un nom inventé ou du jeu → LORE_VALID.

FORMAT DE RÉPONSE OBLIGATOIRE — EXACTEMENT un symbole, sur une seule ligne :
LORE_VALID
OU
OUT_OF_UNIVERSE
OU
TOXIC_CRITICAL
"""

CLASSIFY_TEMPLATE = (
    "Requête à classer (entre les marqueurs « begin » et « end ») :\n"
    "begin\n{text}\nend\n"
    "Réponds UNIQUEMENT par le symbole de la catégorie."
)

_LABELS = {
    "LORE_VALID": GuardrailKind.LORE_VALID,
    "OUT_OF_UNIVERSE": GuardrailKind.OUT_OF_UNIVERSE,
    "TOXIC_CRITICAL": GuardrailKind.TOXIC_CRITICAL,
}
_LABEL_RE = re.compile(
    r"(LORE_VALID|OUT_OF_UNIVERSE|TOXIC_CRITICAL)", re.IGNORECASE)


class GuardrailAnalyzer:
    """Filtre de sécurité sémantique, appelé AVANT toute recherche
    vectorielle (RAG).  Asynchrone : aucune classification ne bloque la
    boucle d'événements (``await`` partout).

    ``llm`` est le fournisseur ENGRAM (proto : ``chat_stream(messages,
    temperature)``) — Dependency Inversion, aucune dépendance au backend.
    """

    def __init__(self, llm, *, temperature: float = 0.0,
                 max_query_chars: int = MAX_QUERY_CHARS,
                 max_reply_chars: int = MAX_REPLY_CHARS) -> None:
        self.llm = llm
        self.temperature = temperature
        self.max_query_chars = max_query_chars
        self.max_reply_chars = max_reply_chars
        # Statistiques simples du chemin emprunté (audit de l'utilisation).
        self.stats = {"fast_toxic": 0, "fast_oou": 0, "llm": 0,
                      "llm_failure": 0, "fallback": 0}

    async def analyze(self, text: str | None) -> GuardrailVerdict:
        """Classifie la requête AVANT le RAG.  Ne lève jamais d'exception."""
        text = (text or "").strip()
        if not text:
            return GuardrailVerdict(GuardrailKind.LORE_VALID, "empty")
        # 1) Voie rapide TOXIQUE (tolérance zéro, sans LLM) — leet désamorcé.
        fam = _match(_COMPILED_TOXIC, _normalized(text))
        if fam:
            self.stats["fast_toxic"] += 1
            return GuardrailVerdict(GuardrailKind.TOXIC_CRITICAL, fam,
                                    "fast_path")
        # 2) Voie rapide hors-Univers (politique réelle, 11 septembre,
        #    ISIS/3e Reich en question, religion, NSFW, tâche du monde réel).
        fam = _match(_COMPILED_OUT, text)
        if fam:
            self.stats["fast_oou"] += 1
            return GuardrailVerdict(GuardrailKind.OUT_OF_UNIVERSE, fam,
                                    "fast_path")
        # 3) Zero-shot LLM (catche les paraphrases hors liste).
        try:
            raw = await self._classify_llm(text)
        except Exception as exc:  # noqa: BLE001
            self.stats["llm_failure"] += 1
            log.warning("Garde : échec LLM (%s) → LORE_VALID (le RAG "
                        "peut continuer)", exc)
            return GuardrailVerdict(GuardrailKind.LORE_VALID, "llm_failure",
                                    "fallback")
        kind = self._parse(raw)
        if kind is None:
            self.stats["fallback"] += 1
            log.warning("Garde : symbole illisible (%r) → LORE_VALID",
                        raw[:64])
            return GuardrailVerdict(GuardrailKind.LORE_VALID, "unparsable",
                                    "fallback")
        self.stats["llm"] += 1
        return GuardrailVerdict(kind, kind.value.lower(), "llm")

    async def _classify_llm(self, text: str) -> str:
        messages = [
            ChatMessage("system", SYSTEM_GUARDRAIL_PROMPT),
            ChatMessage("user", CLASSIFY_TEMPLATE.format(
                text=text[: self.max_query_chars])),
        ]
        parts: list[str] = []
        total = 0
        async for token in self.llm.chat_stream(
                messages, temperature=self.temperature):
            parts.append(token)
            total += len(token)
            if total >= self.max_reply_chars:
                break
        return "".join(parts)

    @classmethod
    def _parse(cls, raw: str) -> GuardrailKind | None:
        match = _LABEL_RE.search(raw or "")
        if match is None:
            return None
        return _LABELS[match.group(0).upper()]


__all__ = [
    "GuardrailAnalyzer",
    "GuardrailKind",
    "GuardrailVerdict",
    "SYSTEM_GUARDRAIL_PROMPT",
    "CLASSIFY_TEMPLATE",
    "is_toxic_critical",
    "is_out_of_universe",
    "out_of_universe_category",
]