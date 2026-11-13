"""ENGRAM service composition from configuration.

Prepares (only on API process import) the SQLAlchemy async engine, the chat
adapter selected by the LLM port factory, the local embedding provider, then
the RAG (dual-route) and Roleplay services.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from warframe_lore.engram.api.ratelimit import SlidingWindowLimiter
from warframe_lore.engram.config import EngramConfig
from warframe_lore.engram.llm import (
    EmbeddingProvider,
    LMStudioProvider,
    build_llm_provider,
)
from warframe_lore.engram.persona import Persona
from warframe_lore.engram.rag import (
    AliasResolver,
    ArchiveVocabulary,
    CodexRoute,
    CosinusSearch,
    HybridSearch,
    MergedRetriever,
    PromptBuilder,
    QueryRewriter,
    RAGService,
    RetrievalRouter,
    SimulatedCrossEncoderReranker,
    StoryRoute,
    StructuredSearch,
)
from warframe_lore.engram.rag.retrieval.routes.codex import CODEX_TOP_N
from warframe_lore.engram.roleplay import (
    RoleplayService,
    SlidingWindow,
    UserMemoryStore,
)


class Container:
    """Application object graph (engine, LLM, services)."""

    def __init__(self, config: EngramConfig | None = None) -> None:
        self.config = config or EngramConfig.load()
        self.engine: AsyncEngine = create_async_engine(
            self.config.database_url, echo=False
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        # Archive-wide vocabulary: the post-generation gate excuses an entity
        # archived on ANY page, not only in the retrieved passages.
        self.vocabulary = ArchiveVocabulary(sessions=self.sessions)
        self.llm = build_llm_provider(self.config)
        # Embeddings always stay local (BGE-M3), whatever the chat backend:
        # a remote adapter (NIM, Gemini) serves chat only.
        self.embeddings = (self.llm if isinstance(self.llm, EmbeddingProvider)
                           else self._local_embeddings())
        self.aliases = AliasResolver()
        # Hybrid search (RAG Inspector + Codex lexical channel): same alias
        # middleware as RAGService, so both see the expanded query.
        self.search = HybridSearch(
            sessions=self.sessions,
            embeddings=self.embeddings,
            alias_resolver=self.aliases,
        )
        candidates = max(self.config.top_k, CODEX_TOP_N)
        semantic = MergedRetriever(
            CosinusSearch(
                sessions=self.sessions,
                top_k=candidates,
                min_score=self.config.min_score,
            ),
            StructuredSearch(sessions=self.sessions, top_k=candidates),
            top_k=candidates,
        )
        self.router = RetrievalRouter(
            CodexRoute(semantic, self.search, SimulatedCrossEncoderReranker()),
            StoryRoute(self.sessions),
        )
        self.rag = RAGService(
            embeddings=self.embeddings,
            retriever=semantic,
            llm=self.llm,
            prompt_builder=PromptBuilder(
                system_prompt=self._system_prompt(),
                max_context_chars=self.config.max_context_chars,
            ),
            suggestion_min_score=self.config.suggestion_min_score,
            critical_min_score=self.config.critical_min_score,
            query_rewriter=QueryRewriter(llm=self.llm),
            alias_resolver=self.aliases,
            vocabulary=self.vocabulary,
            router=self.router,
        )
        self.roleplay = RoleplayService(
            llm=self.llm,
            window=SlidingWindow(
                max_turns=self.config.max_history_turns,
                max_context_chars=self.config.max_context_chars,
            ),
            system_prompt=self._system_prompt(),
            hostile_prompt=Persona(self.config.system_prompt).system_prompt(
                mode="hostile"
            ),
            story_prompt=Persona(self.config.system_prompt).system_prompt(
                mode="story"
            ),
            temperature=self.config.chat_temperature,
            vocabulary=self.vocabulary,
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
            window_seconds=self.config.rate_limit_rag_window,
        )
        self.ws_limiter = SlidingWindowLimiter(
            max_events=self.config.rate_limit_ws,
            window_seconds=self.config.rate_limit_ws_window,
        )

    def _system_prompt(self) -> str:
        """Persona prompt: editable ``persona/oracle`` file, otherwise default."""
        return Persona(self.config.system_prompt).system_prompt()

    def _local_embeddings(self) -> EmbeddingProvider:
        """Local BGE-M3 provider (chat fields are unused by embeddings)."""
        return LMStudioProvider(
            base_url=self.config.lmstudio_base_url,
            chat_model=self.config.chat_model,
            embedding_model=self.config.embedding_model,
            api_key=self.config.lmstudio_api_key,
            max_tokens=self.config.chat_max_tokens,
        )

    async def aclose(self) -> None:
        """Releases the SQL pool and the LLM HTTP session(s)."""
        await self.llm.close()
        if self.embeddings is not self.llm:
            await self.embeddings.close()
        await self.engine.dispose()
