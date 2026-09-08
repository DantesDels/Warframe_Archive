"""Persona de l'assistant : chargé d'un fichier éditable.

Le système de prompt (personnalité) vit dans ``persona/oracle`` pour être
modifiable à tout moment sans toucher au code.  S'il est absent, on retombe
sur ``EngramConfig.system_prompt``.
"""

from __future__ import annotations

from ..config import PROJECT_ROOT

PERSONA_DIR = PROJECT_ROOT / "persona"
PERSONA_FILENAME = "oracle"
PERSONA_FILE = PERSONA_DIR / PERSONA_FILENAME


class Persona:
    """Charge le prompt système du personnage à partir de son fichier."""

    def __init__(self, fallback: str) -> None:
        self.fallback = fallback

    def system_prompt(self) -> str:
        """Prompt système du persona (fichier externe, sinon ``fallback``)."""
        if PERSONA_FILE.is_file():
            return PERSONA_FILE.read_text(encoding="utf-8").strip()
        return self.fallback


__all__ = ["Persona", "PERSONA_FILE"]