"""Transport d'un tour : reconnexion sur coupure et interruption ``!stop``.

Une coupure ne concatène JAMAIS de fragments ; ``!stop`` coupe le flux WS.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from discord_fakes import (
    CHANNEL_ID,
    POOL_GATEWAY,
    FakeMessage,
    HangGateway,
    ScriptedGateway,
    make_bot,
    run,
)

from warframe_lore.discord.mixins.turn.streaming import THINKING, UNREACHABLE
from warframe_lore.discord.services.transport.stream.streamer import (
    DISCORD_MESSAGE_LIMIT,
)


class ReconnectTests(unittest.TestCase):
    """Coupure de flux : UNE reconnexion, jamais de fragments concaténés."""

    def test_reconnexion_sans_concatenation(self):
        first = ScriptedGateway(tokens=("début perdu ",))
        first.fail_once = True
        second = ScriptedGateway(tokens=("réponse propre",))
        scenario = make_bot(gateway=first)
        with mock.patch(POOL_GATEWAY, lambda url: second):
            scenario.say("bonjour")
        self.assertEqual(scenario.channel.sent[0].content, "réponse propre")
        self.assertEqual(len(second.messages), 1)
        self.assertEqual(scenario.stats["errors"], 0)

    def test_serveur_injoignable_message_explicite(self):
        first = ScriptedGateway()
        first.fail_once = True
        second = ScriptedGateway()
        second.fail_once = True
        scenario = make_bot(gateway=first)
        with mock.patch(POOL_GATEWAY, lambda url: second):
            scenario.say("bonjour", allow_errors=True)
        self.assertEqual(scenario.channel.sent[0].content, UNREACHABLE)
        self.assertEqual(scenario.stats["errors"], 1)


def interrupt_after_first_token(scenario, hang) -> None:
    """Démarre un tour, attend le premier jeton, puis envoie ``!stop``."""

    async def play() -> None:
        turn = asyncio.create_task(scenario.bot.on_message(FakeMessage(
            scenario.channel, content="parle-moi de ta journée",
            author=scenario.stranger)))
        for _ in range(400):
            if hang.messages:
                break
            await asyncio.sleep(0.005)
        await scenario.bot.on_message(FakeMessage(
            scenario.channel, content="!stop", author=scenario.stranger))
        await asyncio.gather(turn, return_exceptions=True)

    run(play())


class InterruptTests(unittest.TestCase):
    """``!stop`` coupe le flux WS (donc la génération) et finalise le message."""

    def test_stop_interrompt_le_tour_en_cours(self):
        hang = HangGateway()
        scenario = make_bot(gateway=hang)
        interrupt_after_first_token(scenario, hang)
        self.assertTrue(hang.closed)
        answer = scenario.channel.sent[0].content
        self.assertNotIn(THINKING, answer)
        self.assertIn("réponse interrompue", answer)
        self.assertIn("début de réponse", answer)
        self.assertIn("Réponse interrompue.", scenario.channel.texts)
        self.assertNotIn(CHANNEL_ID, scenario.bot.state.sessions.gateways)

    def test_stop_sans_tour_en_cours(self):
        scenario = make_bot()
        scenario.say("!stop")
        self.assertIn("Aucune réponse en cours à interrompre.",
                      scenario.channel.texts)

    def test_stop_passe_malgré_le_cooldown_antispam(self):
        # Le tour en cours place l'utilisateur en plein cooldown : sans
        # exemption, ``!stop`` serait ignoré au moment où il sert.
        hang = HangGateway()
        scenario = make_bot(gateway=hang, cooldown=30.0)
        interrupt_after_first_token(scenario, hang)
        self.assertIn("Réponse interrompue.", scenario.channel.texts)


class LongReplyTests(unittest.TestCase):
    """Réponses au-delà de la limite Discord : pagination aux limites de mots."""

    CHUNK = ("Eleanor, la protoframe de l'ère 1999, resta fidèle au clan, liée "
             "à ses camarades par le lien mental.")

    def test_une_longue_reponse_page_au_dela_de_2000(self):
        # Un récit entier arrive en UN seul jeton (voie bufférisée du garde-fou) :
        # le placeholder garde la tête, chaque dépassement part en message suivi.
        story = " ".join([self.CHUNK] * 45)
        self.assertGreater(len(story), 2 * DISCORD_MESSAGE_LIMIT)
        scenario = make_bot(gateway=ScriptedGateway(tokens=(story,)))
        scenario.say("parle-moi de ta journée")
        messages = list(scenario.channel.sent)
        self.assertGreaterEqual(len(messages), 3)
        for message in messages:
            self.assertLessEqual(len(message.content), DISCORD_MESSAGE_LIMIT)
        self.assertEqual("".join(m.content for m in messages), story)
        # Aucune coupe en plein mot : chaque page (sauf la dernière) finit sur
        # un séparateur, et la suite reprend exactement au caractère suivant.
        delivered = 0
        for message in messages[:-1]:
            delivered += len(message.content)
            self.assertIn(story[delivered - 1], (" ", "\n"))

    def test_une_reponse_courte_reste_un_seul_message(self):
        scenario = make_bot()
        scenario.say("parle-moi de ta journée")
        self.assertEqual(len(scenario.channel.sent), 1)
        self.assertEqual(scenario.channel.sent[0].content, "Bonjour, organique.")


if __name__ == "__main__":
    unittest.main()
