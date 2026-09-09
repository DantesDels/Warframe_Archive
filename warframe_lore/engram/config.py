"""Configuration d'ENGRAM : connexions, modèles, fenêtres de session."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..envfile import load_dotenv

load_dotenv()


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass
class EngramConfig:
    """Paramètres du backend ENGRAM (RAG + Roleplay).

    Toutes les valeurs sont surchargeables par variables d'environnement
    ``ENGRAM_*``.  Les modèles visent LM Studio local (endpoint compatible
    OpenAI) : embedding ``BAAI/bge-m3`` (GGUF) et chat
    ``Gemma-2-9b-it`` (gguf Q4_K_M) — obéissant aux balises XML et aux
    directives, tenant en 8 Go de VRAM.
    """

    # --- Connexions ---
    database_url: str = field(
        default_factory=lambda: _env(
            "WF_DATABASE_URL",
            "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore",
        ))
    lmstudio_base_url: str = field(
        default_factory=lambda: _env("ENGRAM_LLM_BASE", "http://localhost:1234/v1"))
    lmstudio_api_key: str = field(
        default_factory=lambda: _env("ENGRAM_LLM_KEY", "lm-studio"))

    # --- Modèles ---
    # Chat : Gemma-2-9b-it (gguf Q4_K_M) — meilleure obéissance aux formats
    # XML et aux directives que le 3B ; ~5 Go de VRAM, compatible 8 Go.
    chat_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_CHAT_MODEL", "gemma-2-9b-it"))
    # Température basse → répondes fidèles et déterministes.
    chat_temperature: float = float(_env("ENGRAM_CHAT_TEMP", "0.3"))
    # Borne de génération : garde sous le budget contexte du modèle 9B.
    chat_max_tokens: int = int(_env("ENGRAM_MAX_TOKENS", "2048"))
    embedding_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_EMBED_MODEL", "text-embedding-baai-bge-m3-568m"))
    embedding_dim: int = int(_env("ENGRAM_EMBED_DIM", "1024"))

    # --- RAG ---
    # VRAM 8 Go : contexte strict → seulement les 3 passages les plus proches
    # (~1000-1500 tokens max), sinon débordement mémoire (OOM).
    top_k: int = int(_env("ENGRAM_TOP_K", "3"))

    min_score: float = float(_env("ENGRAM_MIN_SCORE", "0.35"))

    # Seuil de désambiguïsation : sous ce score, la recherche est jugée trop
    # faible pour fonder une réponse ; on tente la suggestion « Voulez-vous
    # dire… » avant le court-circuit.
    suggestion_min_score: float = float(
        _env("ENGRAM_SUGGEST_MIN_SCORE", "0.5"))

    # Seuil critique de réponse : sous ce score, le LLM n'est JAMAIS appelé
    # (court-circuit immédiat, chaîne '[Archives] Données insuffisantes…').
    # Par défaut identique au seuil de suggestion, calibré sur le corpus réel
    # (Lettie 0.55-0.63, Orokin 0.59-0.61, Albrecht 0.52-0.53).
    critical_min_score: float = float(
        _env("ENGRAM_CRITICAL_MIN_SCORE", "0.5"))

    # --- Anti-DDoS / anti-abuse (débit API, fenêtre par IP) ---
    # Route RAG : 30 requêtes/min ; Roleplay WS : 20 connexions/min.
    rate_limit_rag: int = int(_env("ENGRAM_RATE_LIMIT_RAG", "30"))
    rate_limit_rag_window: float = float(_env("ENGRAM_RATE_WINDOW", "60"))
    rate_limit_ws: int = int(_env("ENGRAM_RATE_LIMIT_WS", "20"))
    rate_limit_ws_window: float = float(_env("ENGRAM_RATE_WS_WINDOW", "60"))
    # --- Roleplay (sliding window) ---
    max_history_turns: int = int(_env("ENGRAM_MAX_TURNS", "20"))
    # ~1100 tokens (fr) : sous la limite stricte de 1000-1500 tokens du modèle.
    max_context_chars: int = int(_env("ENGRAM_MAX_CTX_CHARS", "4500"))
    system_prompt: str = field(
        default_factory=lambda: (
            "Tu es Oracle, voix du Cephalon de l'archive WARFRAME. Réponds en "
            "t'appuyant uniquement sur le contexte fourni."))

    @classmethod
    def load(cls) -> "EngramConfig":
        """Construit une configuration depuis l'environnement."""
        return cls()