"""Service RAG documentaire : embedding -> récupération -> prompt -> LLM.

Haut niveau : ne dépend que d'abstractions injectées (``EmbeddingProvider``,
``Retriever``, ``LLMProvider``) — jamais d'un stockage ou d'un client concret
(principe D).  Le point d'accès aux données vit derrière :class:`Retriever`.
Audit : chaque requête journalise le contexte extrait de pgvector avant son
envoi au LLM, pour isoler un manque de données (ETL) d'une désobéissance
du modèle.  Short-circuit : sans passage de confiance, le LLM n'est jamais
appelé — la chaîne exacte :const:`RAG_ERROR` est retournée directement.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from ..llm import EmbeddingProvider, LLMProvider
from ..models import ChatMessage
from .aliases import resolve_alias
from .probes import detect_probe
from .prompt import (JAILBREAK_REJECT, NO_DATA_MARKER, PromptBuilder, RAG_ERROR,
                     RAGPrompt)
from .retriever import RAGHit, Retriever

log = logging.getLogger("warframe_lore.engram.rag")

# Température d'inférence RAG : 0.1 -> analytique/déterministe sans bloquer
# le moteur (Gemma-2-9b-it Q4_K_M sur 8 Go de VRAM).
RAG_TEMPERATURE = 0.1

# Repères anaphoriques : une question qui renvoie au message précédent
# (« …cette histoire de PS5 dit juste avant ? ») récupère mal en vectoriel car
# elle ne nomme aucune entité.  On réutilise alors la dernière requête pour
# enrichir la RECHERCHE (jamais le texte vu par le modèle, qui reste le
# message de l'utilisateur).
_ANAPHORIC = re.compile(
    r"^(et\s+|d'ailleurs\s+)?(cette\b|cet\b|cette histoire\b|cette chose\b|"
    r"ce sujet\b|celui[- ]ci|celui[- ]là|celles?[- ]ci|celles?[- ]là|"
    r"il\b|elle\b|ils\b|elles\b|ça\b|cela\b)",
    re.IGNORECASE)

_ANAPHORIC_MARKERS = (
    "juste avant", "cette histoire", "cette chose", "ce sujet",
    "parlé de", "dit juste", "comme je disais", "comme tu disais",
)

# Caractères de contrôle (hors tabulation/sauts légitimes après split) :
# aucune injection de contrôle dans les embeddings ni dans les logs.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_MAX_QUERY_LEN = 2000

# Jetons Discord (@utilisateur, #canal, emojis personnalisés) : neutralisés
# en amont pour qu'aucun snowflake ne soit jamais reflété par le LLM dans sa
# réponse (anti echo-ping d'un utilisateur tiers).
_MENTION_TOKENS = re.compile(r"<@!?\d+>|<#\d+>|<a?:[a-z0-9_]+:\d+>",
                             re.IGNORECASE)


def sanitize_query(text: str) -> str:
    """Assainit une entrée utilisateur avant recherche/vectorisation :
    retire les caractères de contrôle, normalise les espaces et borne la
    longueur.  Les mentions Discord sont remplacées par un libellé neutre.
    Ne sert AUCUNE interpolation SQL — toutes les requêtes passent par
    SQLAlchemy paramétré (anti-SQLi par construction).
    """
    cleaned = _CONTROL_CHARS.sub(" ", str(text))
    cleaned = _MENTION_TOKENS.sub("un utilisateur", cleaned)
    return " ".join(cleaned.split())[:_MAX_QUERY_LEN]


def _is_anaphoric(question: str) -> bool:
    """Vrai si la question pointe vers le message précédent sans entité."""
    q = question.strip().lower()
    if not q or len(q) > 120:
        return False
    if any(marker in q for marker in _ANAPHORIC_MARKERS):
        return True
    return bool(_ANAPHORIC.match(q))


class RAGService:
    """Orchestre une requête RAG documentaire de bout en bout."""

    def __init__(self, embeddings: EmbeddingProvider, retriever: Retriever,
                 llm: LLMProvider, prompt_builder: PromptBuilder,
                 suggestion_min_score: float = 0.5,
                 critical_min_score: float | None = None) -> None:
        self.embeddings = embeddings
        self.retriever = retriever
        self.llm = llm
        self.prompt_builder = prompt_builder
        self.suggestion_min_score = suggestion_min_score
        # Seuil critique de réponse : sous ce score (typo, sujet hors-corpus),
        # le LLM n'est JAMAIS appelé avec un passage faible.  Calibré sur le
        # corpus réel (Lettie 0.55-0.63, Orokin 0.59-0.61, Albrecht 0.52-0.53).
        # Par défaut : identique au seuil de désambiguïsation.
        self.critical_min_score = critical_min_score
        self._last_query: str | None = None

    async def retrieve(self, question: str
                       ) -> tuple[list[RAGHit], RAGPrompt, bool]:
        """Assemble le prompt et décide du short-circuit, avec journalisation.

        La requête est d'abord enrichie par ``resolve_alias`` (surnom -> nom
        canonique) pour fiabiliser l'embedding.  ``bypass`` signale l'absence
        de passage de confiance ET de désambiguïsation : le LLM ne doit pas
        être appelé (short-circuit).
        """
        question = sanitize_query(question)
        if not question:
            # Entrée vide/non-significative : abstention immédiate ?→ le LLM
            # n'est jamais appelé.
            prompt = self.prompt_builder.build("", [], alias_note="",
                                               suggestion=None)
            log.info("Audit RAG question=%r hit=0 suggestion=None bypass=True "
                     "ctx_car=%d ctx=%r...", question, len(prompt.context),
                     prompt.context[:180].replace("\n", " "))
            return [], prompt, True
        if detect_probe(question):
            # Sondage hostile (injection SQL, escalade de privilèges, mention
            # tiers) : rejet DÉTERMINISTE, sans embedding, sans pgvector, sans
            # LLM.  La même charge utile ne consume donc AUCUN coût et n'entre
            # jamais dans la mémoire de requête.
            prompt = self.prompt_builder.build(question, [], alias_note="",
                                               suggestion=None)
            prompt.rejected = True
            log.warning("Audit RAG question=%r SONDE_HOSTILE bypass=True "
                        "rejected=True (aucun appel modèle)", question)
            return [], prompt, True
        expanded, alias_note, canon = resolve_alias(question)
        # Mémoire de requête : une question anaphorique (« cette histoire… dit
        # juste avant ? ») ne nomme aucune entité -> on réutilise la dernière
        # question pour enrichir la recherche vectorielle uniquement.
        search_question = question
        if self._last_query and _is_anaphoric(question):
            search_question = f"{self._last_query} {question}"
        query_vector = (await self.embeddings.embed([search_question]))[0]
        hits = await self.retriever.search(query_vector)
        floor = (self.suggestion_min_score if self.critical_min_score is None
                 else max(self.critical_min_score, self.suggestion_min_score))
        # Seuil de pertinence : aucun passage sous ``floor`` (ex : fautes de
        # frappe, sujets hors-corpus) ne doit atteindre le LLM. On filtre
        # d'abord, donc ``top`` reflète la force du meilleur passage conservé.
        used_hits = [h for h in hits if h.score >= floor]
        top = used_hits[0].score if used_hits else 0.0
        suggestion = None
        if top < floor:
            # Recherche trop faible (sujet absent, typo…) : ne jamais fonder
            # une réponse sur des voisins hors-sujet.  Le contexte est VIDÉ ;
            # on tente la désambiguïsation (alias canonique ou titre voisin),
            # sinon on coupe court sans jamais appeler le LLM.
            suggestion = (canon if alias_note
                          else await self._suggest_title(question))
            # Contexte privé de contenu : pas de voisin hors-sujet au LLM.
            used_hits = []
        bypass = not used_hits and suggestion is None
        if not bypass:
            # Sujet réellement établi : seule base légitime d'enrichissement
            # pour une future question anaphorique.  Une requête court-circuitée
            # (bypass) ne mémorise RIEN — sinon le sujet absent polluerait la
            # suivante (« cette histoire… » reprenant « souris verte »).
            self._last_query = question
        prompt = self.prompt_builder.build(
            question, used_hits, alias_note=alias_note, suggestion=suggestion)
        note = " search_q=%r" % (search_question,) if search_question != question else ""
        log.info("Audit RAG question=%r%s hit=%d suggestion=%r bypass=%s "
                 "ctx_car=%d ctx=%r...",
                 question, note, len(hits), suggestion, bypass,
                 len(prompt.context), prompt.context[:180].replace("\n", " "))
        return used_hits, prompt, bypass

    async def resolve(self, question: str
                      ) -> tuple[str | None, str | None]:
        """Contexte/suggestion pour un tour Roleplay (WS).

        ``bypass`` -> ``(None, None)`` : le client WS doit alors short-circuiter
        avec la chaîne d'erreur exacte.  Sinon ``(contexte, suggestion)`` : le
        contexte est sûr (jamais de marqueur vide) ; une ``suggestion`` non nulle
        indique au routeur qu'il concerne la désambiguïsation.
        """
        _, prompt, bypass = await self.retrieve(question)
        if bypass:
            return None, None
        return prompt.context, prompt.suggestion

    async def answer_with_sources(self, question: str
                                  ) -> tuple[str, list[RAGHit]]:
        """Réponse du modèle + passages pertinents (short-circuit sinon)."""
        hits, prompt, bypass = await self.retrieve(question)
        if prompt.rejected:
            return JAILBREAK_REJECT, []
        if bypass:
            return RAG_ERROR, []
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        chunks: list[str] = []
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            chunks.append(token)
        return "".join(chunks), hits

    async def stream_answer(self, question: str) -> AsyncIterator[str]:
        """Itère les tokens de la réponse (erreur exacte si short-circuit)."""
        _, prompt, bypass = await self.retrieve(question)
        if prompt.rejected:
            yield JAILBREAK_REJECT
            return
        if bypass:
            yield RAG_ERROR
            return
        messages = [ChatMessage(m["role"], m["content"])
                    for m in prompt.to_messages()]
        async for token in self.llm.chat_stream(messages, RAG_TEMPERATURE):
            yield token

    async def _suggest_title(self, question: str) -> str | None:
        """Nom de page proche du lexique de la question, ou None."""
        suggest = getattr(self.retriever, "suggest_title", None)
        if suggest is None:
            return None
        return await suggest(question)