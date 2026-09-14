"""Verdicts 👍 / 👎 sur les réponses diffusées (ledger persistant).

Chaque réponse streamée est ouverte aux deux verdicts ; une réaction est
enregistrée par utilisateur et par message (un changement remplace le verdict
précédent).  Seules les réponses SUIVIES par le bot comptent : une réaction sur
n'importe quel autre message du salon est ignorée.
"""

from __future__ import annotations

import unittest

from discord_fakes import BOT_ID, CHANNEL_ID, ReactionEvent, make_bot, run

from warframe_lore.discord.mixins.moderation.feedback import (
    REACTION_DOWN,
    REACTION_UP,
)
from warframe_lore.discord.services import VERDICT_DOWN, VERDICT_UP

CELEBRATION = "\U0001f389"


def react(scenario, message_id: int, user_id: int, emoji: str) -> None:
    """Déclenche ``on_raw_reaction_add`` avec un évènement factice."""
    run(scenario.bot.on_raw_reaction_add(
        ReactionEvent(message_id, user_id, CHANNEL_ID, emoji)))


def verdict_of(scenario, message_id: int, user_id: int):
    """Verdict enregistré pour ce couple message/utilisateur (ou ``None``)."""
    return scenario.bot.services.feedback.verdict(message_id, user_id)


class FeedbackTests(unittest.TestCase):
    def test_les_deux_verdicts_sont_proposés(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        self.assertEqual(scenario.channel.sent[0].reactions,
                         [REACTION_UP, REACTION_DOWN])

    def test_verdict_enregistré_puis_remplacé(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        answer = scenario.channel.sent[0]
        stranger = scenario.stranger.id
        react(scenario, answer.id, stranger, REACTION_UP)
        self.assertEqual(verdict_of(scenario, answer.id, stranger), VERDICT_UP)
        react(scenario, answer.id, stranger, REACTION_DOWN)
        self.assertEqual(verdict_of(scenario, answer.id, stranger),
                         VERDICT_DOWN)
        self.assertEqual(scenario.bot.services.feedback.tally(),
                         {VERDICT_UP: 0, VERDICT_DOWN: 1})

    def test_deux_utilisateurs_comptés_séparément(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        answer = scenario.channel.sent[0]
        react(scenario, answer.id, scenario.stranger.id, REACTION_UP)
        react(scenario, answer.id, scenario.creator.id, REACTION_DOWN)
        self.assertEqual(scenario.bot.services.feedback.tally(),
                         {VERDICT_UP: 1, VERDICT_DOWN: 1})

    def test_emoji_inconnu_ignoré(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        answer = scenario.channel.sent[0]
        react(scenario, answer.id, scenario.stranger.id, CELEBRATION)
        self.assertIsNone(verdict_of(scenario, answer.id, scenario.stranger.id))

    def test_message_non_suivi_ignoré(self):
        scenario = make_bot()
        react(scenario, 999999, scenario.stranger.id, REACTION_UP)
        self.assertEqual(scenario.bot.services.feedback.tally(),
                         {VERDICT_UP: 0, VERDICT_DOWN: 0})

    def test_propres_réactions_du_bot_ignorées(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        answer = scenario.channel.sent[0]
        react(scenario, answer.id, BOT_ID, REACTION_UP)
        self.assertIsNone(verdict_of(scenario, answer.id, BOT_ID))

    def test_verdict_visible_dans_stats(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        answer = scenario.channel.sent[0]
        react(scenario, answer.id, scenario.stranger.id, REACTION_UP)
        scenario.say("!stats", author=scenario.creator)
        self.assertIn(f"1 {REACTION_UP}", scenario.channel.last.content)


if __name__ == "__main__":
    unittest.main()
