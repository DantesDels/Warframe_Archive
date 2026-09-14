"""Activity-derived indices of the matriciel card.

Single responsibility (mixin): compute the "Niveau de Sécurité", the
reliability index and the relative assiduité as REAL functions of the
persistent ledger and of the moderation counters — never a LLM guess.
Embed rendering lives in :mod:`embed`.
"""

from __future__ import annotations

from warframe_lore.engram.auth import (
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
    STATUT_ORGANIQUE,
)

# "Niveau de Sécurité" flavour label, derived from the accredited status.
_SECURITY_LEVELS = {
    STATUT_CONCEPTEUR: "Commandement Suprême",
    STATUT_HAUT_COMMANDEMENT: "Commandement Tactique",
    STATUT_MEMBRE_OFFICIEL: "Accès Membre Officiel",
    STATUT_ALLIE: "Accès Invité",
    STATUT_ORGANIQUE: "Accès Invité Restreint",
}

# Assiduité percentile thresholds, best label first.
_ASSIDUITY_TIERS = ((80, "Très assidu"), (60, "Assidu"), (40, "Modéré"),
                    (20, "Peu assidu"))


class CardIndicesMixin:
    """Security level, reliability and assiduité (mixed into the service)."""

    def security_level(self, status: str | None) -> str:
        """Flavour label of the accredited status (guest default)."""
        return _SECURITY_LEVELS.get(status, _SECURITY_LEVELS[STATUT_ORGANIQUE])

    def reliability(self, member_id: int) -> tuple[str, str]:
        """Reliability index from the bot's OWN counters.

        Activity (persistent total), insolence strikes and hostile-probe
        strikes.  Returns ``(label, reason)`` — a pure function.
        """
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
        """Relative assiduité on a 5-level scale (percentile of the ledger)."""
        activity = self.activity.count(member_id)
        if activity == 0:
            return "Inactif", "aucune activité enregistrée"
        others = [count for uid, count in self.activity.all_counts().items()
                  if uid != member_id]
        if not others:
            return "Modéré", "aucune base de comparaison"
        behind = sum(1 for count in others if count < activity)
        percentile = round(100 * behind / len(others))
        label = self._assiduity_label(percentile)
        return label, (f"plus actif que {percentile}% des membres "
                       f"({activity} messages)")

    @staticmethod
    def _assiduity_label(percentile: int) -> str:
        for threshold, label in _ASSIDUITY_TIERS:
            if percentile >= threshold:
                return label
        return "Inactif"


__all__ = ["CardIndicesMixin", "_SECURITY_LEVELS"]
