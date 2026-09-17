"""ENGRAM configuration: connections, models, session windows."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..envfile import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class EngramConfig:
    """ENGRAM backend parameters (RAG + Roleplay).

    All values can be overridden via ``ENGRAM_*`` environment variables.
    Models target local LM Studio (OpenAI-compatible endpoint): embedding
    ``BAAI/bge-m3`` (GGUF) and chat ``Gemma-2-9b-it`` (gguf Q4_K_M) —
    compliant with XML tags and directives, fitting within 8 GB VRAM.
    """

    # --- Connections ---
    database_url: str = field(
        default_factory=lambda: _env(
            "WF_DATABASE_URL",
            "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore",
        ))
    lmstudio_base_url: str = field(
        default_factory=lambda: _env("ENGRAM_LLM_BASE", "http://localhost:1234/v1"))
    lmstudio_api_key: str = field(
        default_factory=lambda: _env("ENGRAM_LLM_KEY", "lm-studio"))

    # --- Models ---
    # Chat: Gemma-2-9b-it (gguf Q4_K_M) — better compliance with XML formats
    # and directives than the 3B; ~5 GB VRAM, compatible with 8 GB.
    chat_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_CHAT_MODEL", "gemma-2-9b-it"))
    # Low temperature → faithful and deterministic responses.
    chat_temperature: float = float(_env("ENGRAM_CHAT_TEMP", "0.3"))
    # Generation cap: high enough for the exhaustive Codex files (long lore
    # answers must not be truncated mid-sentence), yet small enough to fit the
    # model window.  gemma-2 tops out at 8192 tokens and the assembled prompt
    # already measures ~5900 (the persona alone is ~4600), so the former 4096
    # asked for ~10000 tokens and the engine answered "Context size has been
    # exceeded".  2048 leaves ~230 tokens of headroom and still covers 4x the
    # observed sheet length (~500 tokens).
    chat_max_tokens: int = int(_env("ENGRAM_MAX_TOKENS", "2048"))
    embedding_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_EMBED_MODEL", "text-embedding-baai-bge-m3-568m"))
    embedding_dim: int = int(_env("ENGRAM_EMBED_DIM", "1024"))

    # --- RAG ---
    # 8 GB VRAM: strict context → only the 3 closest passages
    # (~1000-1500 tokens max), otherwise out-of-memory (OOM).
    top_k: int = int(_env("ENGRAM_TOP_K", "3"))

    min_score: float = float(_env("ENGRAM_MIN_SCORE", "0.35"))

    # Disambiguation threshold: below this score, the search is deemed too
    # weak to ground a response; the "Did you mean..." suggestion is
    # attempted before short-circuiting.
    suggestion_min_score: float = float(
        _env("ENGRAM_SUGGEST_MIN_SCORE", "0.5"))

    # Critical response threshold: below this score, the LLM is NEVER called
    # (immediate short-circuit, string '[Archives] Insufficient data...').
    # Default identical to the suggestion threshold, calibrated on real corpus
    # (Lettie 0.55-0.63, Orokin 0.59-0.61, Albrecht 0.52-0.53).
    critical_min_score: float = float(
        _env("ENGRAM_CRITICAL_MIN_SCORE", "0.5"))

    # --- Anti-DDoS / anti-abuse (API rate, per-IP window) ---
    # RAG route: 30 requests/min; Roleplay WS: 20 connections/min.
    rate_limit_rag: int = int(_env("ENGRAM_RATE_LIMIT_RAG", "30"))
    rate_limit_rag_window: float = float(_env("ENGRAM_RATE_WINDOW", "60"))
    rate_limit_ws: int = int(_env("ENGRAM_RATE_LIMIT_WS", "20"))
    rate_limit_ws_window: float = float(_env("ENGRAM_RATE_WS_WINDOW", "60"))
    # --- Roleplay (sliding window) ---
    max_history_turns: int = int(_env("ENGRAM_MAX_TURNS", "20"))
    # ~1100 tokens (fr): below the model's strict 1000-1500 token limit.
    max_context_chars: int = int(_env("ENGRAM_MAX_CTX_CHARS", "4500"))

    # --- Per-user short-term memory (mission-6) ---
    # Sliding window kept per ``message.author.id``: the X last
    # request/reply pairs of each speaker.
    memory_pairs: int = int(_env("ENGRAM_MEMORY_PAIRS", "4"))
    # Inactivity expiry: a silent user's history is wiped after Y minutes.
    memory_expiry_seconds: float = float(
        _env("ENGRAM_MEMORY_EXPIRY", "1800"))
    # LRU cap: bounds the store so memory never saturates the process.
    memory_max_users: int = int(_env("ENGRAM_MEMORY_MAX_USERS", "64"))

    system_prompt: str = field(
        default_factory=lambda: (
            "Tu es Oracle, voix du Cephalon de l'archive WARFRAME. Réponds en "
            "t'appuyant uniquement sur le contexte fourni."))

    @classmethod
    def load(cls) -> EngramConfig:
        """Builds a configuration from environment variables."""
        return cls()
