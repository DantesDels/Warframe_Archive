"""Tables volatiles du bot : toutes bornées, aucune croissance avec le guild.

``BotState`` est le seul endroit mutable du bot (hors sessions réseau).
"""

from __future__ import annotations

import unittest

from discord_fakes import run

from warframe_lore.discord.core import (
    MAX_ANSWERS,
    MAX_LAST_MEMBERS,
    MAX_REFUSAL_USERS,
    MAX_STORY_MODES,
    BotState,
)
from warframe_lore.discord.guild import StoryMode
from warframe_lore.discord.services import MemberSnapshot


class RefusalTests(unittest.TestCase):
    def test_compteur_de_refus_par_membre(self):
        state = BotState()
        self.assertEqual(state.refusal_strike(1, "aze07"), 1)
        self.assertEqual(state.refusal_strike(1, "aze07"), 2)
        self.assertEqual(state.refusal_strike(1, "kael"), 1)

    def test_oubli_d_un_refus(self):
        state = BotState()
        state.refusal_strike(1, "aze07")
        state.forget_refusal(1, "aze07")
        self.assertEqual(state.refusal_strike(1, "aze07"), 1)
        state.forget_refusal(42, "inconnu")     # utilisateur jamais vu
        self.assertEqual(state.refusal_strike(42, "aze07"), 1)

    def test_table_bornée(self):
        state = BotState()
        for user_id in range(MAX_REFUSAL_USERS + 10):
            state.refusal_strike(user_id, "aze07")
        self.assertLessEqual(len(state.refusals), MAX_REFUSAL_USERS)


class AnaphoraTests(unittest.TestCase):
    def test_dernier_membre_vu_par_salon(self):
        state = BotState()
        state.remember_member(7, MemberSnapshot(display="Aze07"))
        state.remember_member(8, MemberSnapshot(display="Kael"))
        self.assertEqual(state.last_snapshot(7).display, "Aze07")
        self.assertEqual(state.last_snapshot(8).display, "Kael")

    def test_membre_inconnu_non_mémorisé(self):
        state = BotState()
        state.remember_member(1, None)
        state.remember_member(1, MemberSnapshot())
        self.assertIsNone(state.last_snapshot(1))

    def test_table_bornée(self):
        state = BotState()
        for channel_id in range(MAX_LAST_MEMBERS + 5):
            state.remember_member(channel_id, MemberSnapshot(display="Aze07"))
        self.assertLessEqual(len(state.last_member), MAX_LAST_MEMBERS)


class AnswerTrackingTests(unittest.TestCase):
    def test_salon_d_une_réponse_suivie(self):
        state = BotState()
        state.remember_answer(11, 7)
        self.assertEqual(state.answer_channel(11), 7)
        self.assertIsNone(state.answer_channel(12))

    def test_table_bornée(self):
        state = BotState()
        for message_id in range(MAX_ANSWERS + 5):
            state.remember_answer(message_id, 7)
        self.assertLessEqual(len(state.answers), MAX_ANSWERS)
        self.assertEqual(state.answer_channel(MAX_ANSWERS + 4), 7)
        self.assertIsNone(state.answer_channel(0))


class StoryMemoryTests(unittest.TestCase):
    """Ancrage d'un récit : mémorisé par salon, REPRIS par son seul auteur."""

    def test_ancrage_retenu_pour_son_auteur(self):
        state = BotState()
        mode = StoryMode(request="raconte l'histoire de Ballas")
        state.remember_story(7, 42, mode)
        self.assertEqual(state.story_progress(7, 42), (mode, 0))
        self.assertIsNone(state.story_progress(7, 43))  # un autre organique
        self.assertIsNone(state.story_progress(8, 42))  # un autre salon

    def test_le_curseur_avance_avec_les_parties(self):
        state = BotState()
        mode = StoryMode(request="raconte l'histoire de Ballas")
        state.remember_story(7, 42, mode)
        state.advance_story(7, 42, 12)
        self.assertEqual(state.story_progress(7, 42), (mode, 12))
        state.advance_story(7, 99, 24)          # un autre organique : ignoré
        self.assertEqual(state.story_progress(7, 42), (mode, 12))
        state.advance_story(8, 42, 24)          # un autre salon : ignoré
        self.assertEqual(state.story_progress(7, 42), (mode, 12))

    def test_un_nouveau_recit_remplace_l_ancien(self):
        state = BotState()
        state.remember_story(7, 42, StoryMode(request="un"))
        state.advance_story(7, 42, 12)
        state.remember_story(7, 42, StoryMode(request="deux"))
        progress = state.story_progress(7, 42)
        self.assertEqual(progress[0].request, "deux")
        self.assertEqual(progress[1], 0)        # récit neuf : curseur neuf

    def test_table_bornée(self):
        state = BotState()
        for channel_id in range(MAX_STORY_MODES + 5):
            state.remember_story(channel_id, 42, StoryMode(request="un"))
        self.assertLessEqual(len(state.story_modes), MAX_STORY_MODES)


class TurnTrackingTests(unittest.TestCase):
    def test_tour_courant_d_un_salon(self):
        state = BotState()

        async def scenario() -> None:
            async with state.lock(7):
                state.begin_turn(7)
                self.assertIsNotNone(state.turn(7))
                state.end_turn(7)
            self.assertIsNone(state.turn(7))

        run(scenario())

    def test_verrou_stable_par_salon(self):
        state = BotState()
        self.assertIs(state.lock(7), state.lock(7))
        self.assertIsNot(state.lock(7), state.lock(8))


if __name__ == "__main__":
    unittest.main()
