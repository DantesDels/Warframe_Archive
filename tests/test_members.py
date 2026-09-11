"""Résolution des pseudonymes du serveur (mission : organiques externes).

Le bot reconnaît un Membre du Clan dans le texte ("Qui est Aze ?") — exact ou
abréviation de préfixe ("Aze" → "Aze07") — pour ne JAMAIS l'envoyer au RAG
("Données insuffisantes" du playtest) et répondre via le protocole déterministe
désinvolte.  Les mentions Discord (<@ID>) sont normalisées en noms AVANT la
sonde hostile (un ping de membre légitime n'est pas une attaque echo-ping).

Fonctions pures : aucun objet discord.py requis.
"""

from __future__ import annotations

import unittest

from warframe_lore.discord.members import (
    creator_mentioned,
    creator_pseudo_variants,
    is_member_question,
    match_member_token,
    normalize_mentions,
    roles_question,
)
from warframe_lore.engram.rag.probes import detect_probe


class MatchMemberTokenTests(unittest.TestCase):
    def test_nom_exact_insensible_a_la_casse(self):
        self.assertEqual(match_member_token("Qui est Aze07 ?", ["Aze07"]),
                         "aze07")

    def test_abreviation_prefixe_reconnue(self):
        # 'Aze' (3 car.) est un préfixe de 'Aze07' → résolu.
        self.assertEqual(match_member_token("Qui est Aze ?",
                                            ["Aze07", "Kael"]), "aze")

    def test_pseudo_inconnu_non_resolu(self):
        # 'Lettie' n'est pas un membre → le lore RAG reste applicable.
        self.assertIsNone(match_member_token("Qui est Lettie ?", ["Aze07"]))

    def test_mots_de_fonction_jamais_abreves(self):
        # 'est' n'échappe jamais au stopword pour matcher 'Esteban'.
        self.assertIsNone(match_member_token("Quel est le rôle des Tenno ?",
                                             ["Esteban", "Tenna"]))

    def test_mention_normalisee_matche_le_membre(self):
        text = normalize_mentions("Qui est <@999993> ?", {"999993": "Aze07"})
        self.assertEqual(text, "Qui est Aze07 ?")
        self.assertEqual(match_member_token(text, ["Aze07"]), "aze07")


class MemberQuestionTests(unittest.TestCase):
    def test_qui_est_membre(self):
        self.assertTrue(is_member_question("Qui est Aze ?", "aze"))

    def test_que_sais_tu_sur_le_membre(self):
        self.assertTrue(is_member_question("Que sais-tu sur Aze07 ?", "aze07"))

    def test_parle_moi_de(self):
        self.assertTrue(is_member_question("Parle-moi de Aze ?", "aze"))

    def test_simple_mention_pas_une_question(self):
        # "Aze spamme" : simple allusion → chat libre (persona), pas
        # d'interception déterministe.
        self.assertFalse(is_member_question("Aze n'arrête pas de spammer",
                                            "aze"))

    def test_que_peux_tu_me_dire_sur(self):
        self.assertTrue(is_member_question("Que peux-tu me dire sur Aze ?",
                                           "aze"))

    def test_rapport_matriciel(self):
        self.assertTrue(is_member_question(
            "Donne moi le rapport matriciel de Aze", "aze"))

    def test_fiche_de(self):
        self.assertTrue(is_member_question("fiche de Aze", "aze"))

    def test_informations_sur(self):
        self.assertTrue(is_member_question("informations sur Aze07", "aze07"))

    def test_dis_moi_tout_sur(self):
        self.assertTrue(is_member_question("dis-moi tout sur Aze", "aze"))


class MentionNormalizationTests(unittest.TestCase):
    def test_mention_de_membre_ne_declenche_pas_la_sonde_hostile(self):
        # Playtest bug : "Qui est @Aze07" → anti-jailbreak à tort.
        # Une fois normalisé en nom de membre, la sonde ne doit plus rien
        # voir qui ressemble à un ping tiers.
        raw = "Qui est <@888844> ?"
        self.assertTrue(detect_probe(raw))
        text = normalize_mentions(raw, {"888844": "Aze07"})
        self.assertFalse(detect_probe(text))

    def test_id_inconnu_non_normalise_reste_hostile(self):
        # Mention d'un utilisateur non résolu : toujours un risque d'echo-ping.
        raw = "Qui est <@777755> ?"
        self.assertTrue(detect_probe(normalize_mentions(raw, {"888844": "A"})))

    def test_id_manquant_laisse_inchange(self):
        self.assertEqual(normalize_mentions("Bonjour <@1234>", None),
                         "Bonjour <@1234>")


class CreatorPseudoVariantsTests(unittest.TestCase):
    def test_variantes_derivees_du_display(self):
        self.assertEqual(creator_pseudo_variants("DantesDels"),
                         ["dantesdels", "dantes", "dels"])

    def test_pas_de_variantes_sans_display(self):
        self.assertEqual(creator_pseudo_variants(""), [])
        self.assertEqual(creator_pseudo_variants(None), [])


class CreatorMentionedTests(unittest.TestCase):
    """Jalousie (décision concepteur) : un non-Créateur évoquant le pseudo du
    Concepteur — toutes graphies / toutes majuscules — doit être détecté."""

    def test_nom_complet_toutes_majuscules(self):
        self.assertEqual(creator_mentioned("DANTESDELS", "DantesDels"),
                         "DantesDels")

    def test_tete_mixte(self):
        self.assertEqual(creator_mentioned("DantEs m'a saoulé",
                                           "DantesDels"), "Dantes")

    def test_tete_majuscules(self):
        self.assertEqual(creator_mentioned("salut DANTEs", "DantesDels"),
                         "Dantes")

    def test_queue_majuscules(self):
        self.assertEqual(creator_mentioned("DelS c'est qui ?", "DantesDels"),
                         "Dels")

    def test_mention_dans_une_question(self):
        self.assertEqual(creator_mentioned("Mais qui est DantesDels ?",
                                           "DantesDels"), "DantesDels")

    def test_mot_contenant_le_pseudo_non_detecte(self):
        # "models" contient "dels" mais pas comme mot (pas de frontière) —
        # aucun faux positif sur du vocabulaire organique.
        self.assertIsNone(creator_mentioned("j'ai lu vos petits models",
                                            "DantesDels"))
        self.assertIsNone(creator_mentioned("infantes et dantistes",
                                            "DantesDels"))

    def test_aucune_mention_non_detectee(self):
        self.assertIsNone(creator_mentioned("qui est Aze ?", "DantesDels"))

    def test_display_vide_none(self):
        self.assertIsNone(creator_mentioned("DantesDels", ""))


class RolesQuestionTests(unittest.TestCase):
    """Routage des demandes de rôles (membre explicite vs anaphore)."""

    def test_roles_de_membre_explicite(self):
        self.assertEqual(roles_question("Regarde les rôles de lulu", "lulu"),
                         "member")

    def test_quels_roles_a_membre(self):
        self.assertEqual(roles_question("Quels rôles a Tom.Pass ?",
                                         "tom.pass"), "member")

    def test_ses_roles_anaphore(self):
        self.assertEqual(roles_question("Quels sont ses rôles ?", None),
                         "last")

    def test_son_role_anaphore(self):
        self.assertEqual(roles_question("quel est son rôle ici ?", None),
                         "last")

    def test_aucun_vocabulaire_de_role(self):
        self.assertIsNone(roles_question("comment vas-tu ?", None))
        self.assertIsNone(roles_question("Qui est Aze ?", "aze"))


if __name__ == "__main__":
    unittest.main()