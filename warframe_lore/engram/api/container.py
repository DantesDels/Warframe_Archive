"""ENGRAM service composition from configuration.

Prepares (only on API process import) the SQLAlchemy async engine,
the LM Studio LLM/embedding provider, then the RAG and Roleplay services.
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
from ..rag import (AliasResolver, CosinusSearch, HybridSearch,
                   PromptBuilder, RAGService, QueryRewriter)
from ..roleplay import (RoleplayService, SlidingWindow, UserMemoryStore)
from .ratelimit import SlidingWindowLimiter


class Container:
    """Application object graph (engine, LLM, services)."""

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
            critical_min_score=self.config.critical_min_score,
            query_rewriter=QueryRewriter(llm=self.llm),
        )
        # Hybrid search (RAG Inspector): same alias middleware as RAGService,
        # so the inspector reflects exactly what the vectorization sees.
        self.search = HybridSearch(
            sessions=self.sessions,
            embeddings=self.llm,
            alias_resolver=self.rag.alias_resolver,
        )
        self.roleplay = RoleplayService(
            llm=self.llm,
            window=SlidingWindow(max_turns=self.config.max_history_turns,
                                 max_context_chars=self.config.max_context_chars),
            system_prompt=self._system_prompt(),
            hostile_prompt=Persona(self.config.system_prompt)
                .system_prompt(mode="hostile"),
            temperature=self.config.chat_temperature,
        )
        # Per-user short-term memory: sliding pairs, inactivity expiry, LRU.
        self.memory = UserMemoryStore(
            max_pairs=self.config.memory_pairs,
            expiry_seconds=self.config.memory_expiry_seconds,
            max_users=self.config.memory_max_users,
        )
        # Anti-DDoS / anti-abuse: max rate per IP (HTTP RAG + WS Roleplay).
        self.rag_limiter = SlidingWindowLimiter(
            max_events=self.config.rate_limit_rag,
            window_seconds=self.config.rate_limit_rag_window)
        self.ws_limiter = SlidingWindowLimiter(
            max_events=self.config.rate_limit_ws,
            window_seconds=self.config.rate_limit_ws_window)

    def _system_prompt(self) -> str:
        """Persona prompt: editable ``persona/oracle`` file, otherwise default."""
        return Persona(self.config.system_prompt).system_prompt()

    async def aclose(self) -> None:
        """Releases the SQL pool and the LLM HTTP session."""
        await self.llm.close()
        await self.engine.dispose()