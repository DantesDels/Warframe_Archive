"""Décision de routage d'un tour : frame WS exacte et label d'audit.

``TurnContext`` est une donnée pure (aucun objet Discord) : la frame du contrat
partagé avec ENGRAM et le label compté par ``TurnStats`` en sont des fonctions
directes.  Aucun snowflake de rôle ne part sur le câble — seulement le statut
accrédité et le booléen ``creator``.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.guild.roles import Accreditation
from warframe_lore.discord.mixins.turn.plan import (
    KIND_CREATOR_INSULT,
    KIND_CREATOR_MENTION,
    KIND_FREE,
    KIND_INTROSPECTION,
    KIND_LORE,
    KIND_MEMBER_CARD,
    KIND_MEMBER_MENTION,
    TurnContext,
)
from warframe_lore.discord.services import ChannelSettings
from warframe_lore.engram.auth import STATUT_CONCEPTEUR, STATUT_ORGANIQUE

CREATOR = Accreditation(status=STATUT_CONCEPTEUR, creator=True)
INTROSPECTION = "Qui es-tu, Oracle ?"


def context(**changes) -> TurnContext:
    """Un tour minimal (chat libre, organique, réglages par défaut)."""
    base = {"text": "bonjour", "settings": ChannelSettings(),
            "accr": Accreditation()}
    base.update(changes)
    return TurnContext(**base)


class FrameTests(unittest.TestCase):
    def test_frame_minimale(self):
        frame = context().frame().payload()
        self.assertEqual(frame["type"], "message")
        self.assertEqual(frame["text"], "bonjour")
        self.assertFalse(frame["rag"])
        self.assertEqual(frame["role_status"], STATUT_ORGANIQUE)
        self.assertEqual(frame["lang"], "fr")
        self.assertNotIn("creator_mention", frame)    # None = hors du câble

    def test_langue_du_salon_dans_la_frame(self):
        frame = context(settings=ChannelSettings(lang="en")).frame().payload()
        self.assertEqual(frame["lang"], "en")

    def test_statut_et_rôles_dérivés(self):
        frame = context(user_roles=("CLAN", "PRIME"), user_id=42,
                        accr=CREATOR).frame().payload()
        self.assertEqual(frame["user_roles"], ["CLAN", "PRIME"])
        self.assertTrue(frame["creator"])
        self.assertEqual(frame["role_status"], STATUT_CONCEPTEUR)
        self.assertEqual(frame["user_id"], 42)

    def test_liste_de_rôles_vide_absente_du_câble(self):
        self.assertNotIn("user_roles", context(user_roles=()).frame().payload())

    def test_jalousie_transmise_au_serveur(self):
        frame = context(creator_mention="Dantes").frame().payload()
        self.assertEqual(frame["creator_mention"], "Dantes")


class AuditKindTests(unittest.TestCase):
    def test_labels_de_routage(self):
        self.assertEqual(context().kind, KIND_FREE)
        self.assertEqual(context(use_rag=True).kind, KIND_LORE)
        self.assertEqual(context(member_name="Aze07").kind, KIND_MEMBER_MENTION)
        self.assertEqual(context(text=INTROSPECTION).kind, KIND_INTROSPECTION)

    def test_insulte_du_concepteur(self):
        self.assertEqual(context(insult=True, accr=CREATOR).kind,
                         KIND_CREATOR_INSULT)

    def test_insulte_d_un_organique_n_est_pas_un_tour(self):
        # La répartie est jouée avant le routage : jamais ce label.
        self.assertEqual(context(insult=True).kind, KIND_FREE)

    def test_jalousie_prime_sur_le_membre(self):
        self.assertEqual(context(creator_mention="Dantes",
                                 member_name="DantesDels").kind,
                         KIND_CREATOR_MENTION)

    def test_label_de_carte_membre(self):
        self.assertEqual(KIND_MEMBER_CARD, "member_card")


if __name__ == "__main__":
    unittest.main()
