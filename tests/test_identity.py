"""Réponses d'identité DÉTERMINISTES (mission-7 / playtest) : « qui suis-je »,
« quel est mon rôle » sont répondues depuis les données d'accréditation, pas
par le LLM (le persona CAS A se présente lui-même au lieu de présenter
l'utilisateur). Aucun snowflake ne figure dans ces réponses."""

from __future__ import annotations

import unittest

from warframe_lore.engram.persona import (
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
)
from warframe_lore.engram.roleplay.identity import (
    external_organic_reply,
    identity_reply,
)


class IdentityReplyTests(unittest.TestCase):
    def test_concepteur_nomme_l_utilisateur_et_ses_roles(self):
        reply = identity_reply("DantesDels", None,
                               ["FONDATEUR", "CHEFS DE CLAN"],
                               STATUT_CONCEPTEUR, creator=True)
        self.assertIn("Vous êtes DantesDels, le Concepteur", reply)
        self.assertIn("FONDATEUR", reply)
        self.assertIn("CHEFS DE CLAN", reply)
        self.assertIn("—", reply)  # glitch CAS A

    def test_haut_commandement_defere_institutionnelle(self):
        reply = identity_reply("U", "MODÉRATEURS",
                               [STATUT_HAUT_COMMANDEMENT],
                               STATUT_HAUT_COMMANDEMENT, creator=False)
        self.assertIn("Vous êtes U", reply)
        self.assertIn("Haut Commandement", reply)
        self.assertIn("respect tactique", reply)

    def test_membre_officiel(self):
        reply = identity_reply("U", None, ["CLAN"],
                               STATUT_MEMBRE_OFFICIEL, creator=False)
        self.assertIn("Membre officiel du Clan", reply)
        self.assertNotIn("Concepteur", reply)

    def test_allie(self):
        reply = identity_reply("U", "ALLIANCE", None,
                               STATUT_ALLIE, creator=False)
        self.assertIn("Allié du Système", reply)
        self.assertIn("accès d'invité", reply)

    def test_organique_default(self):
        reply = identity_reply("U", None, None, None, creator=False)
        self.assertIn("organique non-affilié", reply)

    def test_inconnu_sans_identite_retourne_none(self):
        self.assertIsNone(identity_reply(None, None, None, None))

    def test_noms_propres_preserves_et_vides_filtres(self):
        # Le bot n'envoie QUE les NOMS des rôles (jamais les snowflakes) :
        # verify that empty entries are dropped and real names preserved.
        reply = identity_reply("DantesDels", None,
                               ["FONDATEUR", "", "  CHEFS DE CLAN  "],
                               STATUT_CONCEPTEUR, creator=True)
        self.assertIn("FONDATEUR, CHEFS DE CLAN", reply)
        self.assertNotIn("  CHEFS", reply)


class ExternalOrganicReplyTests(unittest.TestCase):
    def test_reponse_factuelle_denigrante(self):
        reply = external_organic_reply("Aze07", creator=False)
        self.assertIn("un organique affilié au Clan", reply)
        self.assertIn("sans intérêt pour la Matrice", reply)
        self.assertNotIn("Concepteur", reply)

    def test_vers_le_concepteur_pointe_de_jalousie_froide(self):
        reply = external_organic_reply("Aze", creator=True)
        self.assertIn("organique affilié au Clan", reply)
        self.assertIn("Concepteur", reply)

    def test_aucune_affection_pour_lexterne(self):
        reply = external_organic_reply("Aze07", creator=False)
        self.assertNotIn("honneur", reply)
        self.assertNotIn("servir", reply)


if __name__ == "__main__":
    unittest.main()