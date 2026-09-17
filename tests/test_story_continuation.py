"""Suivi d'un récit : « continue » rejoue l'ancrage du récit ouvert.

Le suivi n'était ni un récit ni une question de lore : il partait donc en chat
libre — sans ``<archives>``, donc SANS gate — et le persona « fiche Codex »
inventait une page entière (playtest : « Raconte moi l'histoire de ballas »
puis « continue »).  Le bot mémorise l'ancrage par salon et par AUTEUR, et le
suivi rejoue la requête qui a ancré le récit pour la RECHERCHE.
"""

from __future__ import annotations

import unittest

from discord_fakes import make_bot

from warframe_lore.discord.guild import LENS_INITIATE, LENS_QUESTION

BALLAS = "Raconte moi l'histoire de ballas"


class ContinuationRoutingTests(unittest.TestCase):
    def test_un_suivi_rejoue_l_ancrage_du_recit(self):
        scenario = make_bot()
        scenario.say(BALLAS)
        story_frame = scenario.gateway.messages[-1]
        self.assertTrue(story_frame["story"])

        scenario.say("continue")
        frame = scenario.gateway.messages[-1]
        self.assertEqual(frame["text"], "continue")
        self.assertTrue(frame["story"])
        self.assertTrue(frame["rag"])
        self.assertEqual(frame["targeted_era"], story_frame["targeted_era"])
        self.assertEqual(frame["targeted_subject"],
                         story_frame["targeted_subject"])
        self.assertEqual(frame["retrieval_text"], BALLAS)

    def test_un_suivi_reprend_la_lentille_choisie(self):
        scenario = make_bot()
        scenario.say("raconte moi une histoire")
        self.assertEqual(scenario.channel.last.content, LENS_QUESTION)
        scenario.say("1")
        self.assertEqual(scenario.gateway.messages[-1]["story_lens"],
                         LENS_INITIATE)

        scenario.say("continue")
        frame = scenario.gateway.messages[-1]
        self.assertTrue(frame["rag"])
        self.assertEqual(frame["story_lens"], LENS_INITIATE)

    def test_un_suivi_sans_recit_ouvert_reste_en_chat_libre(self):
        scenario = make_bot()
        scenario.say("continue")
        frame = scenario.gateway.messages[-1]
        self.assertFalse(frame["story"])
        self.assertFalse(frame["rag"])
        self.assertNotIn("retrieval_text", frame)

    def test_un_autre_membre_ne_reprend_pas_le_recit(self):
        scenario = make_bot()
        scenario.say(BALLAS)
        scenario.say("continue", author=scenario.creator)
        frame = scenario.gateway.messages[-1]
        self.assertFalse(frame["story"])
        self.assertNotIn("retrieval_text", frame)


if __name__ == "__main__":
    unittest.main()
