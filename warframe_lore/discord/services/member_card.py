"""Member-card service: the deterministic RAPPORT MATRICIEL embed.

Pure, dependency-light rendering (discord.py for the embed only): the
Niveau de Sécurité, the reliability index and the relative assiduité are
REAL functions of accredited data and of the persistent activity ledger —
never a LLM guess.  The LLM behavioural analysis is fetched upstream
(``RoleplayGateway.comment``) and passed to :meth:`MemberCardService.build`.

Extracted from the monolithic bot so the card logic is unit-testable and the
routing lives alone in :mod:`warframe_lore.discord.bot`.
"""

from __future__ import annotations

import discord

from warframe_lore.engram.auth import (
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
    STATUT_ORGANIQUE,
)

from ..moderation.hostility import HostilityTracker
from .activity import MemberActivityStore

# "Niveau de Sécurité" flavour label of the member card, derived from the
# accredited Discord status (never a LLM guess).
_SECURITY_LEVELS = {
    STATUT_CONCEPTEUR: "Commandement Suprême",
    STATUT_HAUT_COMMANDEMENT: "Commandement Tactique",
    STATUT_MEMBRE_OFFICIEL: "Accès Membre Officiel",
    STATUT_ALLIE: "Accès Invité",
    STATUT_ORGANIQUE: "Accès Invité Restreint",
}


class MemberCardService:
    """Builds the member cards and the activity-derived indices."""

    def __init__(self, activity: MemberActivityStore,
                 insolence: HostilityTracker,
                 probes: HostilityTracker) -> None:
        self.activity = activity
        self.insolence = insolence
        self.probes = probes

    def security_level(self, status: str | None) -> str:
        """"Niveau de Sécurité" flavour label from the accredited status."""
        return _SECURITY_LEVELS.get(status, _SECURITY_LEVELS[STATUT_ORGANIQUE])

    def reliability(self, member_id: int) -> tuple[str, str]:
        """Real reliability index from the bot's own counters: activity
        (persistent total), insolence strikes and hostile-probe strikes.
        Returns ``(label, reason)`` — a pure function, never the LLM's guess."""
        activity = self.activity.count(member_id)
        insolence = self.insolence.count(member_id)
        probes = self.probes.count(member_id)
        if probes >= 2:
            return "Compromis", "tentatives hostiles répétées"
        if insolence >= 3:
            return "Défaillant", "insolence récurrente"
        if activity == 0:
            return "Inconnu", "aucune interaction enregistrée"
        if activity < 3:
            return "Faible", "interactions trop rares"
        if activity >= 10 and insolence == 0 and probes == 0:
            return "Élevée", "présence régulière, aucune incartade"
        if activity >= 5:
            return "Moyenne", "présence correcte"
        return "Inconstant", "activité irrégulière"

    def assiduity(self, member_id: int) -> tuple[str, str]:
        """Relative assiduité on a 5-level scale: the member's persistent
        activity compared to the OTHER tracked members (percentile).  A real,
        comparable function of the per-member ledger — never a LLM guess."""
        activity = self.activity.count(member_id)
        counts = self.activity.all_counts()
        others = [c for uid, c in counts.items() if uid != member_id]
        if activity == 0:
            return "Inactif", "aucune activité enregistrée"
        if not others:
            return "Modéré", "aucune base de comparaison"
        behind = sum(1 for c in others if c < activity)
        pct = round(100 * behind / len(others))
        if pct >= 80:
            label = "Très assidu"
        elif pct >= 60:
            label = "Assidu"
        elif pct >= 40:
            label = "Modéré"
        elif pct >= 20:
            label = "Peu assidu"
        else:
            label = "Inactif"
        return label, f"plus actif que {pct}% des membres ({activity} messages)"

    def build(self, info: dict, comment: str) -> discord.Embed:
        """Well-formed member card (Discord embed): profile picture beside
        the pseudo, roles as bullets, network ID, security level, reliability
        index and the LLM behavioural analysis."""
        name = info.get("display") or "Inconnu"
        embed = discord.Embed(title="RAPPORT MATRICIEL", color=0x7c3aed)
        avatar = info.get("avatar")
        if avatar:
            embed.set_thumbnail(url=avatar)
        # Pseudo puis identifiant réseau : en sous-titres (h4) juste sous le
        # titre « RAPPORT MATRICIEL ».
        embed.description = (
            f"**IDENTIFIANT :** {name}\n"
            f"**Identifiant Réseau :** #{info.get('member_id') or 'inconnu'}")
        roles = info.get("roles") or []
        roles_txt = "\n".join(f"- {r}" for r in roles) if roles else "- aucun"
        embed.add_field(name="Rôles et Accréditations", value=roles_txt,
                        inline=False)
        embed.add_field(name="Niveau de Sécurité",
                        value=self.security_level(info.get("status")),
                        inline=True)
        a_label, a_reason = self.assiduity(int(info.get("member_id") or 0))
        embed.add_field(name="Assiduité",
                        value=f"{a_label} — {a_reason}", inline=True)
        label, reason = self.reliability(int(info.get("member_id") or 0))
        embed.add_field(name="Indice de Fiabilité",
                        value=f"{label} — {reason}", inline=True)
        if comment:
            embed.add_field(name="Analyse comportementale de la Matrice",
                            value=f"« {comment} »", inline=False)
        return embed


__all__ = ["MemberCardService", "_SECURITY_LEVELS"]
