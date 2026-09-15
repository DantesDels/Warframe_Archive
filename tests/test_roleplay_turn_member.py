"""Décision d'un tour Roleplay : courts-circuits « membre » et « identité ».

Le reste de :mod:`test_roleplay_turn` — une question sur un membre du guild ou
sur l'identité du locuteur est répondue de façon DÉTERMINISTE (rôles réels,
données accréditées), jamais par les archives ni par le modèle.  La persona
hostile ignore ces deux courts-circuits : l'attaquant doit d'abord s'excuser.
"""

from __future__ import annotations

import unittest

from engram_fakes import decide

from warframe_lore.protocols.roleplay import PERSONA_HOSTILE

IDENTITY = "qui suis-je ?"


class MemberReplyTests(unittest.TestCase):
    def test_membre_avec_rôles_répond_le_roster(self):
        plan = decide({"member_name": "Aze07", "member_roles": ["CLAN"],
                       "creator": False})
        self.assertIn("Aze07", plan.reply)
        self.assertIn("CLAN", plan.reply)

    def test_membre_sans_rôles_répond_l_organique_externe(self):
        self.assertIn("Aze07", decide({"member_name": "Aze07",
                                       "reluctant": True}).reply)

    def test_affiliation_réelle_respectée(self):
        plan = decide({"member_name": "Enjoy", "member_roles": [],
                       "member_affiliated": False})
        self.assertIn("non affilié au Clan", plan.reply)


class IdentityReplyTests(unittest.TestCase):
    def test_identité_du_locuteur_déterministe(self):
        plan = decide({"user_name": "DantesDels", "role_status": "Concepteur",
                       "creator": True}, IDENTITY)
        self.assertIn("DantesDels", plan.reply)

    def test_identité_sans_payload_retombe_sur_le_llm(self):
        self.assertIsNone(decide({}, IDENTITY).reply)


class HostilePersonaTests(unittest.TestCase):
    def test_persona_hostile_ignore_membre_et_identité(self):
        cases = ((IDENTITY, {"user_name": "U"}),
                 ("qui est Aze07 ?", {"member_name": "Aze07"}))
        for text, payload in cases:
            plan = decide(payload, text, persona=PERSONA_HOSTILE)
            self.assertIsNone(plan.reply, text)


if __name__ == "__main__":
    unittest.main()
