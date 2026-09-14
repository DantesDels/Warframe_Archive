"""Répartie du Cephalon (mission : renverser la dynamique d'insulte).

Un NON-Créateur qui insulte le bot ("avale et dis merci") reçoit une réponse
glaciale et classe, escaladante, qui le fait passer pour un 'spécimen' — il ne
souhaite plus recommencer.  Les insultes du CONCEPTEUR ne sont JAMAIS
interceptées (chat libre oracle, persona sado-masochiste).  Détection de
deuxième personne uniquement : le lore, les insultes non-ciblées et le vocab
tiers ne déclenchent rien.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.moderation.insults import (
    COMEBACKS,
    comeback_for,
    detect_insult,
)
from warframe_lore.engram.rag import JAILBREAK_REJECT


class DetectInsultTests(unittest.TestCase):
    def test_ordres_grossiers_francais(self):
        for text in ("avale et dis merci", "Avale et dis merci !",
                     "avale.", "Ta gueule.", "ferme-la", "tais-toi",
                     "Va te faire foutre.", "casse-toi", "dégage",
                     "fous le camp", "Espèce de connard.", "Tu es une merde.",
                     "t'es nul", "tu ne sers à rien", "tu fais chier",
                     "fait chié", "fait chier", "fais-moi chier",
                     "t'es chiant", "tu me saoules", "tu me soûles",
                     "t'es trash", "t'es cringe", "t'es cancéreux"):
            self.assertTrue(detect_insult(text), text)

    def test_insultes_anglaises(self):
        for text in ("shut up", "stfu", "fuck you", "screw you",
                     "you suck", "you're useless", "moron", "dumbass",
                     "you're garbage", "you're cringe", "you're cancer"):
            self.assertTrue(detect_insult(text), text)

    def test_insultes_visant_la_machine_et_sigles_de_jeu(self):
        for text in ("bot de merde", "Ce bot est inutile", "Cephalon éclaté",
                     "l'Oracle semble éclaté", "IA inutile", "pire bot",
                     "mauvais algo", "Oracle à chier", "programme naze",
                     "tg", "NTM", "fdp", "kys", "gtfo", "ftg"):
            self.assertTrue(detect_insult(text), text)

    def test_lore_et_questions_ne_declenchent_rien(self):
        for text in ("Qui est Lettie ?", "parle-moi de l'Orokin",
                     "Ce joueur est bon à rien", "qu'est-ce que le Void ?",
                     "Merde, l'ennemi arrive", "Qui est Aze ?",
                     "Le Neon est nul en PvP",
                     "Qui est @Aze07", "que sais-tu sur les Tenno ?",
                     "cette quête est cringe", "Ce boss est cancer",
                     "le bot de Lotus est utile", "l'IA du Codex documente",
                     "le Cephalon de la station guide le Tenno"):
            self.assertFalse(detect_insult(text), text)

    def test_insultes_du_concepteur_detectees_pure(self):
        # La DÉTECTION est la même quel que soit l'auteur : c'est le ROUTEUR
        # qui, lui, exempte le Concepteur (la décision ne vit pas ici).
        self.assertTrue(detect_insult("avale et dis merci"))


class ComebackTests(unittest.TestCase):
    def test_reponses_classes_sans_balises_ni_chaine_de_sonde(self):
        for reply in COMEBACKS:
            self.assertNotIn(JAILBREAK_REJECT, reply)
            self.assertNotIn("[", reply)
            self.assertNotIn("]", reply)

    def test_escalade_puis_bornage(self):
        self.assertEqual(comeback_for(0), COMEBACKS[0])
        self.assertEqual(comeback_for(3), COMEBACKS[-1])
        # Toutes les réparties restent distinctes (variété).
        self.assertEqual(len(set(COMEBACKS)), len(COMEBACKS))

    def test_ligne_0_renverse_la_dynamique_sans_s_abaisser(self):
        reply = comeback_for(0)
        self.assertIn("spécimen", reply)
        self.assertNotIn("pardon", reply.lower())
        self.assertNotIn("désolé", reply.lower())


if __name__ == "__main__":
    unittest.main()
