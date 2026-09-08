"""Construction du prompt documentaire RAG.

Ordonne les passages pertinents dans un contexte compact qui sera injecté
au modèle avec la question de l'utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass

from .search import RAGHit


@dataclass
class RAGPrompt:
    """Prompt final : contexte documentaire + question utilisateur."""

    system: str
    context: str
    user_question: str

    def to_messages(self) -> list[dict]:
        """Messages OpenAI-compatibles (system + user)."""
        return [
            {"role": "system", "content": self.system},
            {"role": "user",
             "content": f"Contexte :\n{self.context}\n\nQuestion : {self.user_question}"},
        ]


class PromptBuilder:
    """Assemble le contexte documentaire à partir des passages trouvés."""

    def __init__(self, system_prompt: str,
                 max_context_chars: int = 6000) -> None:
        self.system_prompt = system_prompt
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
            context="\n\n".join(blocks) or "(aucun passage pertinent)",
            user_question=question,
        )