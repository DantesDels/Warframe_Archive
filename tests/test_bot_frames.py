"""Frame WS d'un tour : texte, accréditation dérivée, décision RAG.

Le bot est piloté par son vrai ``on_message`` (harnais :mod:`discord_fakes`) :
on assertit la frame qui part vers ENGRAM (contrat partagé) et le label d'audit
compté par ``TurnStats``.  Aucun réseau, aucun LLM, aucun disque.
"""

from __future__ import annotations

import unittest

from discord_fakes import CHANNEL_ID, CREATOR_ID, make_bot

from warframe_lore.discord.mixins.moderation.feedback import (
    REACTION_DOWN,
    REACTION_UP,
)
from warframe_lore.engram.auth import STATUT_CONCEPTEUR, STATUT_ORGANIQUE


class FrameTests(unittest.TestCase):
    """La frame ``message`` porte le texte et l'accréditation DÉRIVÉE."""

    def test_chat_libre_sans_rag(self):
        scenario = make_bot()
        scenario.say("bonjour Oracle")
        frame = scenario.gateway.last
        self.assertEqual(frame["type"], "message")
        self.assertEqual(frame["text"], "bonjour Oracle")
        self.assertFalse(frame["rag"])
        self.assertEqual(frame["lang"], "fr")

    def test_réponse_diffusée_puis_ouverte_aux_verdicts(self):
        scenario = make_bot()
        scenario.say("bonjour")
        answer = scenario.channel.sent[0]
        self.assertEqual(answer.content, "Bonjour, organique.")
        self.assertEqual(answer.reactions, [REACTION_UP, REACTION_DOWN])

    def test_accreditation_du_concepteur_dans_la_frame(self):
        scenario = make_bot()
        scenario.say("cause avec moi", author=scenario.creator)
        frame = scenario.gateway.last
        self.assertTrue(frame["creator"])
        self.assertEqual(frame["role_status"], STATUT_CONCEPTEUR)
        self.assertEqual(frame["user_roles"], ["FONDATEUR"])
        self.assertEqual(frame["user_name"], "DantesDels")
        self.assertEqual(frame["user_id"], CREATOR_ID)

    def test_organique_non_affilié(self):
        scenario = make_bot()
        scenario.say("bonjour")
        frame = scenario.gateway.last
        self.assertFalse(frame["creator"])
        self.assertEqual(frame["role_status"], STATUT_ORGANIQUE)

    def test_question_de_lore_active_le_rag(self):
        scenario = make_bot()
        scenario.say("Quelle est l'histoire des Orokin ?")
        self.assertTrue(scenario.gateway.last["rag"])
        self.assertEqual(scenario.stats["by_kind"]["lore"], 1)
        self.assertEqual(scenario.stats["rag_turns"], 1)

    def test_mention_du_concepteur_coupe_le_rag(self):
        scenario = make_bot()
        scenario.say("Mais qui est DantesDels ?")
        frame = scenario.gateway.last
        self.assertEqual(frame["creator_mention"], "DantesDels")
        self.assertFalse(frame["rag"])
        self.assertEqual(scenario.stats["by_kind"]["creator_mention"], 1)

    def test_un_membre_du_guild_ne_part_pas_dans_les_archives(self):
        scenario = make_bot()
        scenario.say("Aze07 spamme encore le salon")
        self.assertFalse(scenario.gateway.last["rag"])
        self.assertEqual(scenario.stats["by_kind"]["member_mention"], 1)
        # Anaphore mémorisée : « Quels sont ses rôles ? » garde son référent.
        self.assertEqual(scenario.bot.state.last_snapshot(CHANNEL_ID).display,
                         "Aze07")

    def test_introspection_jamais_documentaire(self):
        scenario = make_bot()
        scenario.say("Qui es-tu, Oracle ?")
        self.assertFalse(scenario.gateway.last["rag"])
        self.assertEqual(scenario.stats["by_kind"]["introspection"], 1)

    def test_la_persona_du_salon_est_appliquée_une_seule_fois(self):
        scenario = make_bot()
        scenario.say("bonjour", author=scenario.creator)
        scenario.say("encore toi", author=scenario.creator)
        self.assertEqual(scenario.gateway.personas, [])     # oracle = défaut
        scenario.say("!persona hostile", author=scenario.creator)
        scenario.say("bonjour", author=scenario.creator)
        scenario.say("encore", author=scenario.creator)
        self.assertEqual(scenario.gateway.personas, ["hostile"])


if __name__ == "__main__":
    unittest.main()
