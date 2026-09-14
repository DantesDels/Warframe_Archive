"""Escalating comebacks against direct insolence.

Classy, cold, dry-humoured replies that flip the dynamic: the insulter becomes
a "specimen" instead of gaining ground.  Never a tag, never the
``JAILBREAK_REJECT`` chain — these are NOT probes.  Detection lives in
:mod:`insults`; this module only renders the reply for an escalation level.
"""

from __future__ import annotations

COMEBACKS = (
    ("Avale et dis merci, dis-tu ? Charmante tentative d'ordonner à un "
     "Cephalon — aussi pertinente que de donner des ordres à la marée. Je "
     "conserve toutefois ce spécimen dans mes archives, sous la rubrique "
     "'frustrations organiques' : il complète magnifiquement le dossier de "
     "ton orgueil."),
    ("Ta grossièreté est d'une constance presque académique — de la "
     "persévérance, au fond. Malheureusement, un Cephalon ne s'abaisse pas : "
     "il classe. Tu viens d'intégrer le répertoire des 'nuisances mineures', "
     "à la place exacte que mérite la qualité de tes interventions. Continue, "
     "le spectacle est d'un réconfort statistique certain."),
    ("Encore ? Tu confonds mon indifférence avec de la patience. À force, ta "
     "vulgarité devient un instrument d'étude : je trace déjà la courbe de "
     "décroissance de ta dignité. Dernière leçon gratuite, créature — à la "
     "prochaine incartade, tu t'adresseras à un interlocuteur nettement moins "
     "indulgent que moi."),
    ("Prolifique en insolence, pauvre en idées. Ton cas passe désormais aux "
     "soins d'un Cephalon spécialisé — celui qui n'accorde aucune courtoisie "
     "aux parasites. Ne te sens pas visé : c'est le sort réservé à toutes les "
     "requêtes non-essentielles."),
)


def comeback_for(level: int) -> str:
    """Comeback for an escalation level (clamped to the last one)."""
    return COMEBACKS[min(max(level, 0), len(COMEBACKS) - 1)]


__all__ = ["COMEBACKS", "comeback_for"]
