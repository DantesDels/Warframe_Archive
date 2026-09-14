"""Réponses DÉTERMINISTES sur un membre du guild (organique externe).

« Qui est Aze ? » et « rôles de lulu » ne passent ni par les archives (« Données
insuffisantes » au playtest) ni par le modèle (il inventait « Lulu, coordinatrice
/ stratège ») : le texte est construit depuis les rôles Discord RÉELS, avec la
concession « à contrecœur » quand un non-Créateur insiste.
"""

from __future__ import annotations

import unittest

from warframe_lore.engram.roleplay.replies import (
    external_organic_reply,
    member_comment_request,
    member_roster_reply,
)


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

    def test_non_affilie_pas_assume_clan(self):
        # Playtest : « Enjoy ne fait pas partie du clan » — l'affiliation
        # reflète les rôles Discord RÉELS, jamais une supposition.
        reply = external_organic_reply("Enjoy", creator=False,
                                       affiliated=False)
        self.assertIn("non affilié au Clan", reply)
        self.assertNotIn("organique affilié au Clan", reply)

    def test_concession_contrecoeur(self):
        reply = external_organic_reply("Tom.Pass", creator=False,
                                       affiliated=False, reluctant=True)
        self.assertIn("À contrecœur, puisque vous insistez", reply)
        self.assertIn("non affilié au Clan", reply)


class MemberRosterReplyTests(unittest.TestCase):
    def test_fiche_roles_reels(self):
        reply = member_roster_reply("lulu", ["Mascotte", "Allié"],
                                    affiliated=False, creator=True)
        self.assertIn("lulu", reply)
        self.assertIn("Mascotte, Allié", reply)
        self.assertIn("non affilié au Clan", reply)
        self.assertIn("Concepteur", reply)

    def test_aucun_role_annonce_aucun(self):
        reply = member_roster_reply("lulu", [], affiliated=False)
        self.assertIn("aucun", reply)

    def test_concession_contrecoeur_roster(self):
        reply = member_roster_reply("lulu", ["Mascotte"], affiliated=False,
                                    reluctant=True)
        self.assertIn("À contrecœur, puisque vous insistez", reply)


class MemberCommentRequestTests(unittest.TestCase):
    """Matériau de la fiche membre : le commentaire est généré par le modèle
    à partir des rôles RÉELS et des interactions (jamais une formule figée,
    jamais une affiliation affirmée d'office)."""

    def test_contient_le_materiau_brut(self):
        request = member_comment_request(
            "Aze07", ["CHEF DE CLAN", "PRIME"],
            interactions=["Qui est Arthur ?", "Parle-moi de Vena"])
        self.assertIn("Fiche membre : Aze07", request)
        self.assertIn("CHEF DE CLAN, PRIME", request)
        self.assertIn("Rôles réels", request)
        self.assertIn("N'affirme AUCUNE affiliation", request)
        self.assertNotIn("affilié au Clan", request)
        self.assertIn("- Qui est Arthur ?", request)
        self.assertIn("- Parle-moi de Vena", request)

    def test_aucune_interaction_explicite(self):
        request = member_comment_request("lulu", [], interactions=None)
        self.assertIn("(aucune interaction enregistrée)", request)

    def test_audience_concepteur_et_concession(self):
        request = member_comment_request(
            "Tom.Pass", [], interactions=[], creator=True, reluctant=True)
        self.assertIn("ton Concepteur", request)
        self.assertIn("cédé à contrecœur", request)


if __name__ == "__main__":
    unittest.main()
