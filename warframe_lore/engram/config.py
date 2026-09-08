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
    ``Llama-3.2-3B-Instruct`` (non-raisonant, rapide pour le Roleplay).
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
    chat_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_CHAT_MODEL", "llama-3.2-3b-instruct"))
    # Température basse → rôleplay fidèle et déterministe sur modèle 3B.
    chat_temperature: float = float(_env("ENGRAM_CHAT_TEMP", "0.3"))
    # Borne de génération : garde sous le budget contexte du modèle 3B.
    chat_max_tokens: int = int(_env("ENGRAM_MAX_TOKENS", "2048"))
    embedding_model: str = field(
        default_factory=lambda: _env(
            "ENGRAM_EMBED_MODEL", "text-embedding-baai-bge-m3-568m"))
    embedding_dim: int = int(_env("ENGRAM_EMBED_DIM", "1024"))

    # --- RAG ---
    # Modèles 3B : contexte strict → seulement les 3 passages les plus proches.
    top_k: int = int(_env("ENGRAM_TOP_K", "3"))
    min_score: float = float(_env("ENGRAM_MIN_SCORE", "0.35"))

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