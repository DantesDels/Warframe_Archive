"""Role hierarchy & speaker accreditation (mission-8).

Facade: re-exports the hierarchy types so every caller keeps importing
``warframe_lore.discord.guild.roles`` (the discovery CLI lives in ``dump``).
"""

from __future__ import annotations

from .hierarchy import Accreditation, RoleHierarchy

__all__ = ["Accreditation", "RoleHierarchy"]
