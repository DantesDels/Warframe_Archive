"""Fiche membre (card Discord) : indice de fiabilité RÉEL, niveau de sécurité
et mise en page de l'embed — sans connexion Discord (le service de carte est
testé isolément, en pur Python)."""

from __future__ import annotations

import unittest

from warframe_lore.discord.moderation.hostility import HostilityTracker
from warframe_lore.discord.services.activity import MemberActivityStore
from warframe_lore.discord.services.member_card import MemberCardService
from warframe_lore.engram.auth import (
    STATUT_HAUT_COMMANDEMENT,
    STATUT_ORGANIQUE,
)


def _Service():
    """Service de carte monté sur les vrais stores (mémoire SQLite)."""
    activity = MemberActivityStore(":memory:")
    return MemberCardService(
        activity=activity,
        insolence=HostilityTracker(),
        probes=HostilityTracker(),
    )


class ReliabilityTests(unittest.TestCase):
    """L'indice de fiabilité est une vraie fonction des compteurs enregistrés."""

    def setUp(self) -> None:
        self.insolence = HostilityTracker()
        self.probes = HostilityTracker()
        self.activity = MemberActivityStore(":memory:")
        self.card = MemberCardService(
            activity=self.activity, insolence=self.insolence,
            probes=self.probes)

    def test_inconnu_sans_interaction(self):
        self.assertEqual(
            self.card.reliability(1),
            ("Inconnu", "aucune interaction enregistrée"))

    def test_compromis_apres_probes_repetees(self):
        self.probes.strike(1)
        self.probes.strike(1)
        self.assertEqual(self.card.reliability(1)[0], "Compromis")

    def test_defaillant_apres_insolence_recurrente(self):
        for _ in range(3):
            self.insolence.strike(1)
        self.assertEqual(self.card.reliability(1)[0], "Défaillant")

    def test_elevée_activite_reguliere_sans_incartade(self):
        for _ in range(12):
            self.activity.record(1, "message")
        self.assertEqual(
            self.card.reliability(1),
            ("Élevée", "présence régulière, aucune incartade"))

    def test_faible_peu_d_interactions(self):
        self.activity.record(1, "message")
        self.assertEqual(self.card.reliability(1)[0], "Faible")


class SecurityLevelTests(unittest.TestCase):
    def test_mapping_status_vers_niveau(self):
        card = _Service()
        self.assertEqual(card.security_level(STATUT_HAUT_COMMANDEMENT),
                         "Commandement Tactique")
        self.assertEqual(card.security_level(STATUT_ORGANIQUE),
                         "Accès Invité Restreint")
        self.assertEqual(card.security_level(None), "Accès Invité Restreint")


class AssiduityTests(unittest.TestCase):
    """Assiduité RELATIVE sur 5 niveaux : comparée aux autres membres."""

    def setUp(self) -> None:
        self.card = _Service()

    def _seed(self, counts):
        for uid, n in counts.items():
            for _ in range(n):
                self.card.activity.record(uid, "message")

    def test_inactif_sans_activite(self):
        self.assertEqual(self.card.assiduity(1)[0], "Inactif")

    def test_seul_actif_neutral(self):
        self._seed({1: 5})
        self.assertEqual(self.card.assiduity(1)[0], "Modéré")

    def test_tres_assidu(self):
        self._seed({1: 50, 2: 3, 3: 4, 4: 2})
        label, reason = self.card.assiduity(1)
        self.assertEqual(label, "Très assidu")
        self.assertIn("100%", reason)

    def test_assidu(self):
        # bat 7 des 10 autres (les 9) → 70% → "Assidu"
        self._seed({1: 10, 2: 9, 3: 9, 4: 9, 5: 9, 6: 9, 7: 9, 8: 9,
                    9: 15, 10: 15, 11: 15})
        self.assertEqual(self.card.assiduity(1)[0], "Assidu")

    def test_modere(self):
        # bat 2 des 5 autres → 40% → "Modéré"
        self._seed({1: 7, 2: 6, 3: 6, 4: 9, 5: 9, 6: 9})
        self.assertEqual(self.card.assiduity(1)[0], "Modéré")

    def test_peu_assidu(self):
        # bat 1 des 4 autres → 25% → "Peu assidu"
        self._seed({1: 5, 2: 10, 3: 10, 4: 10, 5: 3})
        self.assertEqual(self.card.assiduity(1)[0], "Peu assidu")

    def test_inactif_dernier_du_classement(self):
        # bat 0 des 2 autres → 0% → "Inactif" (niveau le plus bas)
        self._seed({1: 1, 2: 20, 3: 18})
        self.assertEqual(self.card.assiduity(1)[0], "Inactif")


class RoleNamesTests(unittest.TestCase):
    """``_role_names`` doit filtrer @everyone (méthode ``is_default()``) sans
    jeter les vrais rôles."""

    def test_vrais_roles_conserves(self):
        from warframe_lore.discord.bot import LoreMasterBot

        class Role:
            def __init__(self, name, default):
                self.name = name
                self._default = default

            def is_default(self):
                return self._default

        class Member:
            roles = [Role("@everyone", True), Role("CHEF DE CLAN", False),
                     Role("PRIME", False)]

        self.assertEqual(LoreMasterBot._role_names(Member()),
                         ["CHEF DE CLAN", "PRIME"])


class MemberEmbedTests(unittest.TestCase):
    def test_fiche_complete_bien_construite(self):
        card = _Service()
        info = {
            "display": "Aze07",
            "roles": ["CHEF DE CLAN", "PRIME"],
            "affiliated": True,
            "status": STATUT_HAUT_COMMANDEMENT,
            "avatar": "https://cdn.discordapp.com/avatars/1/a.png",
            "member_id": "4829",
        }
        # 12 interactions sans incartade → "Élevée" ; 2 autres membres à 9
        # messages → assiduité 100% (Très assidu / contient "Assidu").
        for _ in range(12):
            card.activity.record(4829, "message")
        for uid in (11, 22):
            for _ in range(9):
                card.activity.record(uid, "message")
        embed = card.build(info, "observation")
        data = embed.to_dict()
        self.assertEqual(data["title"], "RAPPORT MATRICIEL")
        self.assertNotIn("Aze07", data["title"])
        self.assertEqual(data["thumbnail"]["url"],
                         "https://cdn.discordapp.com/avatars/1/a.png")
        fields = {f["name"]: f["value"] for f in data["fields"]}
        self.assertIn("CHEF DE CLAN", fields["Rôles et Accréditations"])
        self.assertIn("PRIME", fields["Rôles et Accréditations"])
        # Pseudo et identifiant réseau : sous-titres sous « RAPPORT MATRICIEL ».
        self.assertIn("IDENTIFIANT :** Aze07", data["description"])
        self.assertIn("Identifiant Réseau", data["description"])
        self.assertIn("#4829", data["description"])
        self.assertNotIn("Identifiant Réseau", fields)
        self.assertIn("Commandement Tactique", fields["Niveau de Sécurité"])
        self.assertIn("assidu", fields["Assiduité"].lower())
        self.assertIn("Élevée", fields["Indice de Fiabilité"])
        self.assertIn("observation",
                      fields["Analyse comportementale de la Matrice"])


if __name__ == "__main__":
    unittest.main()
