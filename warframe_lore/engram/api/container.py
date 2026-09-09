"""Composition des services ENGRAM à partir de la configuration.

Prépare (uniquement à l'import du process API) l'engine SQLAlchemy async,
le fournisseur LLM/embedding LM Studio, puis les services RAG et Roleplay.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from ..config import EngramConfig
from ..llm import LMStudioProvider
from ..persona import Persona
from ..rag import CosinusSearch, PromptBuilder, RAGService
from ..roleplay import RoleplayService, SlidingWindow


class Container:
    """Graphe d'objets de l'application (engine, LLM, services)."""

    def __init__(self, config: EngramConfig | None = None) -> None:
        self.config = config or EngramConfig.load()
        self.engine: AsyncEngine = create_async_engine(
            self.config.database_url, echo=False)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.llm = LMStudioProvider(
            base_url=self.config.lmstudio_base_url,
            chat_model=self.config.chat_model,
            embedding_model=self.config.embedding_model,
            api_key=self.config.lmstudio_api_key,
            max_tokens=self.config.chat_max_tokens,
        )
        self.rag = RAGService(
            embeddings=self.llm,
            retriever=CosinusSearch(
                sessions=self.sessions,
                top_k=self.config.top_k,
                min_score=self.config.min_score),
            llm=self.llm,
            prompt_builder=PromptBuilder(
                system_prompt=self._system_prompt(),
                max_context_chars=self.config.max_context_chars),
            suggestion_min_score=self.config.suggestion_min_score,
        )
        self.roleplay = RoleplayService(
            llm=self.llm,
            window=SlidingWindow(max_turns=self.config.max_history_turns,
                                 max_context_chars=self.config.max_context_chars),
            system_prompt=self._system_prompt(),
            temperature=self.config.chat_temperature,
        )

    def _system_prompt(self) -> str:
        """Prompt du persona : fichier éditable ``persona/oracle`` sinon défaut."""
        return Persona(self.config.system_prompt).system_prompt()

    async def aclose(self) -> None:
        """Libère le pool SQL et la session HTTP du LLM."""
        await self.llm.close()
        await self.engine.dispose()