"""Construction du prompt documentaire RAG.

Ordonne les passages pertinents dans un contexte compact qui sera injecté
au modèle avec la question de l'utilisateur.  Comporte deux garde-fous
anti-hallucination : un marqueur de contexte vide (short-circuit) et une
directive stricte de repli verrouillée dans le prompt système.
"""

from __future__ import annotations

from dataclasses import dataclass

from .search import RAGHit

# Contexte injecté quand aucun passage pertinent n'est remonté. Le modèle est
# censé répondre "je ne sais pas" plutôt que d'inventer.
NO_DATA_MARKER = "[AUCUNE DONNÉE RÉCUPÉRÉE]"

# Verrouillage absolu : ajouté en dur au prompt système, quel que soit le
# persona éditable (ne peut pas être désactivé en modifiant persona/oracle).
HALLUCINATION_GUARD = (
    "DIRECTIVE CRITIQUE : Tu dois répondre en utilisant EXCLUSIVEMENT le "
    "contexte fourni. Si le contexte indique [AUCUNE DONNÉE RÉCUPÉRÉE] ou ne "
    "contient pas la réponse exacte, il t'est STRICTEMENT INTERDIT "
    "d'inventer des informations. Tu dois répondre UNIQUEMENT par la phrase : "
    "\"Mes archives mnémoniques sont corrompues ou incomplètes concernant ce "
    "sujet.\"")


@dataclass
class RAGPrompt:
    """Prompt final : contexte documentaire + question utilisateur."""

    system: str
    context: str
    user_question: str

    def to_messages(self) -> list[dict]:
        """Messages OpenAI-compatibles.

        Réorganisation spécifique aux petits modèles (3B) : le contexte
        documentaire est inséré en premier, et le persona Oracle est placé en
        *dernier*, juste avant le message utilisateur — ainsi les instructions
        de rôle/tòn ne sont pas noyées par un long contexte factuel.
        """
        return [
            {"role": "system",
             "content": f"Contexte documentaire :\n{self.context}"},
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user_question},
        ]


class PromptBuilder:
    """Assemble le contexte documentaire à partir des passages trouvés."""

    def __init__(self, system_prompt: str,
                 max_context_chars: int = 6000) -> None:
        # La directive anti-hallucination est verrouillée ici (en dur), après
        # le persona, pour garantir sa présence sur tous les prompts RAG.
        self.system_prompt = f"{system_prompt}\n\n{HALLUCINATION_GUARD}"
        self.max_context_chars = max_context_chars

    def build(self, question: str, hits: list[RAGHit]) -> RAGPrompt:
        blocks: list[str] = []
        used = 0
        for hit in hits:
            block = f"[{hit.page_title}] {hit.content.strip()}"
            if used + len(block) > self.max_context_chars and blocks:
                break
            used += len(block)
            blocks.append(block)
        return RAGPrompt(
            system=self.system_prompt,
            # Short-circuit : aucun passage pertinent → marqueur explicite
            # plutôt qu'un contexte vide ou ambigu.
            context="\n\n".join(blocks) or NO_DATA_MARKER,
            user_question=question,
        )