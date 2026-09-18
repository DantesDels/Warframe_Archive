"""Suivi d'un récit : « continue » rejoue l'ancrage du récit ouvert.

Le suivi n'était ni un récit ni une question de lore : il partait donc en chat
libre — sans ``<archives>``, donc SANS gate — et le persona « fiche Codex »
inventait une page entière (playtest : « Raconte moi l'histoire de ballas »
puis « continue »).  Le bot mémorise l'ancrage par salon et par AUTEUR, et le
suivi rejoue la requête qui a ancré le récit pour la RECHERCHE.
"""

from __future__ import annotations

import unittest

from discord_fakes import ScriptedGateway, make_bot

from warframe_lore.discord.guild import (
    LENS_INITIATE,
    LENS_QUESTION,
    STORY_AUTO_PARTS,
    STORY_CONTINUATION_PROMPT,
)
from warframe_lore.protocols.roleplay import STORY_DOSSIER_PAGE

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


class AutoChainingTests(unittest.TestCase):
    """Le récit s'enchaîne : chaque partie lit la PAGE SUIVANTE du dossier.

    Une partie ne suffit pas à couvrir un dossier de plusieurs dizaines de
    fragments (~2,5 k caractères par partie) : tant que le serveur annonce
    ``story_more``, le bot enchaîne — jusqu'au plafond ``STORY_AUTO_PARTS``,
    puis rend la parole.
    """

    def test_un_dossier_inepuise_enchaine_des_parties_inédites(self):
        gateway = ScriptedGateway(tokens=("partie.",))
        gateway.story_more = True                   # il reste des fragments
        scenario = make_bot(gateway=gateway)
        scenario.say(BALLAS)
        frames = [m for m in gateway.messages if m.get("story")]
        self.assertEqual(len(frames), STORY_AUTO_PARTS)
        self.assertEqual([f["dossier_offset"] for f in frames],
                         [i * STORY_DOSSIER_PAGE
                          for i in range(STORY_AUTO_PARTS)])
        self.assertEqual(frames[0]["text"], BALLAS)
        self.assertEqual(frames[1]["text"], STORY_CONTINUATION_PROMPT)
        self.assertEqual(frames[1]["retrieval_text"], BALLAS)

    def test_un_dossier_epuise_arrete_l_enchainement(self):
        scenario = make_bot()                       # ``story_more`` false
        scenario.say(BALLAS)
        self.assertEqual(len([m for m in scenario.gateway.messages
                              if m.get("story")]), 1)

    def test_le_curseur_repris_par_un_continue_avance(self):
        gateway = ScriptedGateway(tokens=("partie.",))
        gateway.story_more = True
        scenario = make_bot(gateway=gateway)
        scenario.say(BALLAS)
        gateway.story_more = False
        scenario.say("continue")
        frame = gateway.messages[-1]
        self.assertEqual(frame["retrieval_text"], BALLAS)
        self.assertEqual(frame["dossier_offset"],
                         STORY_AUTO_PARTS * STORY_DOSSIER_PAGE)


if __name__ == "__main__":
    unittest.main()
