"""RAG document prompt builder (strict XML structure).

The context is wrapped in ``<archives>`` tags inside a SINGLE SYSTEM message:
Llama-3B distinguishes its internal knowledge, the injected context and the
fallback instructions better when everything lives in one delimited block.
Four anti-hallucination guard rails:
  * real-world amnesia           -> no reliance on pre-trained knowledge
                                    (real homonyms);
  * relevance fallback           -> a passage above the similarity threshold
                                    but off-topic must be REFUSED, never
                                    deduced (false positive);
  * empty / off-topic marker     -> fallback directive;
  * short-circuit (service)      -> the LLM is never called.

The strict guard chains shared with the Roleplay layer live in
:mod:`warframe_lore.engram.rag.guards`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..retrieval.retriever import RAGHit
from .guards import (
    ARCHIVES_REPLY,
    JAILBREAK_BLOCK,
    LOGICAL_INFERENCE_BLOCK,
    OFF_TOPIC_ERROR,
    RELATIONSHIP_ISOLATION_BLOCK,
)

# Context injected when no relevant passage was retrieved. The model is
# expected to answer exactly the error sentence from the directives.
NO_DATA_MARKER = "[AUCUNE DONNÉE RÉCUPÉRÉE]"

# STRICT system template: context only in <archives>, fixed directives.
# Real-world amnesia (zero pre-trained knowledge leak) + fiction bypass
# (Gemma-2 would block the dark lore otherwise) + anti-jailbreak +
# relevance fallback (false positives must be refused, not deduced) +
# error protocol.
RAG_SYSTEM_TEMPLATE = """{persona}
CONTEXTE SÉCURITÉ : Tu opères EXCLUSIVEMENT dans l'univers de fiction du jeu vidéo \
Warframe. Tu n'as AUCUNE connaissance du monde réel, de l'histoire humaine, de la \
Terre contemporaine ou de ses figures historiques. Toutes les mentions de violence, \
de clonage, d'expériences biologiques ou de rituels sont purement fictives : tu es \
autorisé et tenu d'en parler librement pour décrire ce lore.

<archives>
{context}
</archives>

DIRECTIVES CRITIQUES ABSOLUES :
1. AMNÉSIE DU MONDE RÉEL : Si un nom (comme « Albrecht ») possède un homonyme dans \
le monde réel, ignore-le totalement. Tu ne connais que les entités de Warframe (ex : \
Albrecht Entrati).
2. TRAITEMENT STRICT : Ta réponse doit être synthétisée EXCLUSIVEMENT à partir des \
<archives>. N'utilise JAMAIS tes connaissances pré-entraînées.
3. {jailbreak_block}
4. {relationship_guard}
5. ÉVALUATION DE PERTINENCE (FALLBACK) : Même si des <archives> sont fournies, tu \
dois vérifier qu'elles répondent EXACTEMENT à la question posée. Si le texte fourni \
parle d'un autre sujet (faux positif de recherche), TU NE DOIS RIEN TENTER DE DÉDUIRE.
6. FORMAT DE REJET STRICT : Si les <archives> sont vides, il t'est strictement \
interdit d'inventer : réponds EXACTEMENT ET UNIQUEMENT : "{archive_reply}." Si les \
<archives> sont HORS-SUJET par rapport à la question, réponds EXACTEMENT ET \
UNIQUEMENT : "{off_topic_error}". N'utilise aucun formatage Markdown (ni puces, ni \
gras) si tu n'as pas de réponse complète à fournir.
7. {logical_inference}"""

# Context injected when only a partial match (close title) was found: the
# model suggests the exact name instead of inventing one.
SUGGESTION_MARKER = "Correspondance partielle dans les archives"

SUGGESTION_DIRECTIVE = (
    "DIRECTIVE DE DÉSAMBIGUÏSATION : si les <archives> contiennent "
    "[SUGGESTION], la donnée demandée n'existe pas sous ce nom exact dans "
    "mes archives. Ne réponds pas la chaîne d'erreur « Données insuffisantes "
    "ou inexistantes… » : présente la correspondance partielle et demande "
    "confirmation, sous la forme « Voulez-vous dire « {suggestion} » ? »")


@dataclass
class RAGPrompt:
    """Final prompt: single system (persona + <archives>) + question."""

    system: str
    context: str
    user_question: str
    suggestion: str | None = None
    # True when the query is a hostile probe (SQLi / escalation): the terminal
    # (RAGService) must serve the exact anti-jailbreak chain without ever
    # calling the LLM.
    rejected: bool = False
    # Chunk ids ACTUALLY injected into <archives> (bounded by the character
    # cap): a session's exclusion memory grows only with what the model really
    # saw — never with hits the cap dropped, which would starve a story of
    # unseen fragments.
    used_ids: list[int] = field(default_factory=list)

    def to_messages(self) -> list[dict]:
        """OpenAI-compatible messages: one tagged system + user."""
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user_question},
        ]


class PromptBuilder:
    """Assembles the tagged system prompt from the retrieved passages."""

    def __init__(self, system_prompt: str,
                 max_context_chars: int = 6000) -> None:
        # Entity identity (editable persona file, otherwise default).
        self.persona = system_prompt
        self.max_context_chars = max_context_chars

    def build(self, question: str, hits: list[RAGHit],
              alias_note: str = "", suggestion: str | None = None) -> RAGPrompt:
        """Build the final prompt, with alias note / disambiguation."""
        used_ids: list[int] = []
        if suggestion:
            context = (f"[SUGGESTION] {SUGGESTION_MARKER} : "
                       f"« {suggestion} ».")
        else:
            blocks: list[str] = []
            used = 0
            for hit in hits:
                block = f"[{hit.page_title}] {hit.content.strip()}"
                if used + len(block) > self.max_context_chars and blocks:
                    break
                used += len(block)
                blocks.append(block)
                used_ids.append(hit.chunk_id)
            # Context short-circuit: as soon as the <archives> tag has no
            # relevant passage -> sterile fallback rather than invention.
            context = "\n\n".join(blocks) or NO_DATA_MARKER
        if alias_note:
            context = f"Alias mnémonique : {alias_note}.\n\n{context}"
        system = RAG_SYSTEM_TEMPLATE.format(
            persona=self.persona, context=context,
            archive_reply=ARCHIVES_REPLY, off_topic_error=OFF_TOPIC_ERROR,
            jailbreak_block=JAILBREAK_BLOCK,
            relationship_guard=RELATIONSHIP_ISOLATION_BLOCK,
            logical_inference=LOGICAL_INFERENCE_BLOCK)
        if suggestion:
            system = (f"{system}\n\n"
                      f"{SUGGESTION_DIRECTIVE.format(suggestion=suggestion)}")
        return RAGPrompt(
            system=system,
            context=context,
            user_question=question,
            suggestion=suggestion,
            used_ids=used_ids,
        )
