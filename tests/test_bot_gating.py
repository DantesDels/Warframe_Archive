"""Gating : où le bot parle, et où il se tait.

Le bot n'intervient que sur mention, dans un salon dédié (ou un de ses threads),
ou en message privé ; il se tait sur le hors-caractère, sur un salon désactivé
— mais garde ses commandes, sinon ``!channel on`` serait impossible.
"""

from __future__ import annotations

import unittest

from discord_fakes import CHANNEL_ID, DM_ID, Channel, make_bot


class GatingTests(unittest.TestCase):
    def test_hors_caractere_ignoré(self):
        scenario = make_bot()
        for content in ("(pause cinq minutes)", "// je reviens"):
            scenario.say(content)
        self.assertEqual(scenario.gateway.messages, [])
        self.assertEqual(scenario.channel.sent, [])

    def test_salon_non_dédié_sans_mention_ignoré(self):
        scenario = make_bot()
        other = scenario.use_channel(Channel(555, guild=scenario.guild))
        scenario.say("bonjour tout le monde", channel=other)
        self.assertEqual(scenario.gateway.messages, [])

    def test_sans_restriction_le_bot_repond_dans_tous_les_salons(self):
        scenario = make_bot()
        scenario.bot.allowed_channels = set()
        other = scenario.use_channel(Channel(555, guild=scenario.guild))
        scenario.say("bonjour tout le monde", channel=other)
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_mention_du_bot_hors_salon_dédié(self):
        scenario = make_bot()
        other = scenario.use_channel(Channel(555, guild=scenario.guild))
        scenario.say("bonjour Oracle", channel=other,
                     mentions=[scenario.bot.user])
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_thread_d_un_salon_dédié(self):
        scenario = make_bot()
        thread = scenario.use_channel(
            Channel(666, guild=scenario.guild, parent=Channel(CHANNEL_ID)))
        scenario.say("bonjour", channel=thread)
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_message_privé(self):
        scenario = make_bot()
        private = scenario.use_channel(Channel(DM_ID))
        scenario.say("bonjour", channel=private)
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_salon_désactivé_rend_muet_mais_garde_les_commandes(self):
        scenario = make_bot()
        scenario.say("!channel off", author=scenario.creator)
        self.assertFalse(scenario.settings.get(CHANNEL_ID).enabled)
        scenario.say("bonjour Oracle")
        self.assertEqual(scenario.gateway.messages, [])
        # La commande de réactivation passe malgré le silence du salon.
        scenario.say("!channel on", author=scenario.creator)
        self.assertTrue(scenario.settings.get(CHANNEL_ID).enabled)
        scenario.say("bonjour Oracle")
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_refus_de_spam_selon_le_cooldown(self):
        scenario = make_bot(cooldown=2.5)
        scenario.say("bonjour Oracle")
        scenario.say("encore bonjour")
        self.assertEqual(len(scenario.gateway.messages), 1)

    def test_l_activité_est_consignée_même_hors_réponse(self):
        scenario = make_bot()
        scenario.say("(hors caractère)", author=scenario.creator)
        other = scenario.use_channel(Channel(555, guild=scenario.guild))
        scenario.say("discussion entre joueurs", channel=other)
        activity = scenario.bot.services.activity
        self.assertEqual(activity.count(scenario.creator.id), 1)
        self.assertEqual(activity.count(scenario.stranger.id), 1)


if __name__ == "__main__":
    unittest.main()
