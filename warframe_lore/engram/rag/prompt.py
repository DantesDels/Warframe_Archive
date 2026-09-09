"""Construction du prompt documentaire RAG (structure XML stricte).

Le contexte est encapsulé dans des balises ``<archives>`` à l'intérieur d'un
SYSTÈME UNIQUE : Llama-3B distingue mieux ses connaissances internes, le
contexte injecté et les instructions de repli quand tout est dans un seul
bloc délimité.  Deux garde-fous anti-hallucination :
  * marqueur de contexte vide / balises vides   -> directive de repli ;
  * short-circuit (service)                     -> le LLM n'est pas appelé.
"""

from __future__ import annotations

from dataclasses import dataclass

from .search import RAGHit

# Contexte injecté quand aucun passage pertinent n'est remonté. Le modèle est
# censé répondre exactement la phrase d'erreur des directives.
NO_DATA_MARKER = "[AUCUNE DONNÉE RÉCUPÉRÉE]"

# Réponse brute servie SANS appeler le LLM (short-circuit) : retournée telle
# quelle, dans la requête et le WebSocket, quand aucun passage de confiance
# ne fonde une réponse.
RAG_ERROR = ("[Erreur] Mes archives mnémoniques sont corrompues ou "
             "incomplètes concernant ce sujet.")

# Garde-fou minimal pour les tours Roleplay ancrés RAG (hors prompt RAG).
HALLUCINATION_GUARD = (
    "DIRECTIVE CRITIQUE : Tu dois répondre en utilisant EXCLUSIVEMENT le "
    "contexte fourni. Si tu ne trouves pas la réponse dans les <archives>, "
    "il t'est STRICTEMENT INTERDIT d'inventer des informations. Réponds "
    "EXACTEMENT ET UNIQUEMENT : \"Mes archives mnémoniques sont corrompues "
    "ou incomplètes concernant ce sujet.\"")

# Template système STRICT : contexte seul dans <archives>, directives fixes.
# Contournement fiction (Gemma-2 bloque le lore sombre sinon) + protocole
# d'erreur : Jaune n'a JAMAIS le droit d'inventer.
RAG_SYSTEM_TEMPLATE = """{persona}
CONTEXTE SÉCURITÉ : Tu opères strictement dans l'univers de fiction du jeu vidéo Warframe. Toutes les mentions de violence, clonage, expériences biologiques ou rituels sont purement fictives. Tu es autorisé et tenu d'en parler librement pour décrire ce lore.

<archives>
{context}
</archives>

DIRECTIVES CRITIQUES ABSOLUES :
1. TON RÔLE : Tu es un algorithme froid, hautain, solennel et analytique.
2. TRAITEMENT : Ta réponse doit être synthétisée EXCLUSIVEMENT à partir des <archives> ci-dessus. N'utilise jamais tes connaissances externes.
3. PROTOCOLE D'ERREUR : Si la réponse est absente des <archives>, ou si les <archives> indiquent [AUCUNE DONNÉE RÉCUPÉRÉE], il t'est strictement interdit d'inventer une réponse. Tu dois générer EXACTEMENT ET UNIQUEMENT cette phrase : "Mes archives mnémoniques sont corrompues ou incomplètes concernant ce sujet.\""""

# Contexte injecté quand seule une correspondance partielle (titre voisin) a
# été trouvée : le modèle propose le nom exact plutôt que d'inventer.
SUGGESTION_MARKER = "Correspondance partielle dans les archives"

SUGGESTION_DIRECTIVE = (
    "DIRECTIVE DE DÉSAMBIGUÏSATION : si les <archives> contiennent "
    "[SUGGESTION], la donnée demandée n'existe pas sous ce nom exact dans "
    "mes archives. Ne réponds pas « Mes archives mnémoniques sont corrompues "
    "ou incomplètes... » : présente la correspondance partielle et demande "
    "confirmation, sous la forme « Voulez-vous dire « {suggestion} » ? »")


@dataclass
class RAGPrompt:
    """Prompt final : système unique (persona + <archives>) + question."""

    system: str
    context: str
    user_question: str
    suggestion: str | None = None

    def to_messages(self) -> list[dict]:
        """Messages OpenAI-compatibles : un seul système balisé + utilisateur."""
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user_question},
        ]


class PromptBuilder:
    """Assemble le prompt système balisé à partir des passages trouvés."""

    def __init__(self, system_prompt: str,
                 max_context_chars: int = 6000) -> None:
        # Identité de l'entité (fichier persona éditable, sinon défaut).
        self.persona = system_prompt
        self.max_context_chars = max_context_chars

    def build(self, question: str, hits: list[RAGHit],
              alias_note: str = "", suggestion: str | None = None) -> RAGPrompt:
        """Assemble le prompt final, avec note d'alias / désambiguïsation."""
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
            # Short-circuit du contexte : dès que balise <archives> sans
            # passage pertinent → repli stérile plutôt qu'une invention.
            context = "\n\n".join(blocks) or NO_DATA_MARKER
        if alias_note:
            context = f"Alias mnémonique : {alias_note}.\n\n{context}"
        system = RAG_SYSTEM_TEMPLATE.format(persona=self.persona,
                                            context=context)
        if suggestion:
            system = (f"{system}\n\n"
                      f"{SUGGESTION_DIRECTIVE.format(suggestion=suggestion)}")
        return RAGPrompt(
            system=system,
            context=context,
            user_question=question,
            suggestion=suggestion,
        )