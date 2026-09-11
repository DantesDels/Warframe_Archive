"""Fiche membre (card Discord) : indice de fiabilité RÉEL, niveau de sécurité
et mise en page de l'embed — sans connexion Discord (objet bot minimal)."""

from __future__ import annotations

import unittest

from warframe_lore.discord.bot import LoreMasterBot
from warframe_lore.discord.hostility import HostilityTracker
from warframe_lore.engram.persona import (
    STATUT_HAUT_COMMANDEMENT,
    STATUT_ORGANIQUE,
)


class _Bot(LoreMasterBot):
    """Compteurs seuls — aucun ``discord.Client`` sous-jacent n'est monté."""

    def __init__(self) -> None:
        self._member_activity: dict[int, int] = {}
        self._member_history: dict[int, list[str]] = {}
        self._insults = HostilityTracker()
        self.hostility = HostilityTracker()
        self._member_refusals: dict[int, dict[str, int]] = {}
        self._last_member: dict[int, dict] = {}


class ReliabilityTests(unittest.TestCase):
    """L'indice de fiabilité est une vraie fonction des compteurs enregistrés."""

    def test_inconnu_sans_interaction(self):
        bot = _Bot()
        self.assertEqual(
            bot._reliability(1), ("Inconnu", "aucune interaction enregistrée"))

    def test_compromis_apres_probes_repetees(self):
        bot = _Bot()
        bot.hostility.strike(1)
        bot.hostility.strike(1)
        self.assertEqual(bot._reliability(1)[0], "Compromis")

    def test_defaillant_apres_insolence_recurrente(self):
        bot = _Bot()
        for _ in range(3):
            bot._insults.strike(1)
        self.assertEqual(bot._reliability(1)[0], "Défaillant")

    def test_elevée_activite_reguliere_sans_incartade(self):
        bot = _Bot()
        bot._member_activity[1] = 12
        self.assertEqual(
            bot._reliability(1), ("Élevée", "présence régulière, aucune incartade"))

    def test_faible_peu_d_interactions(self):
        bot = _Bot()
        bot._member_activity[1] = 1
        self.assertEqual(bot._reliability(1)[0], "Faible")


class SecurityLevelTests(unittest.TestCase):
    def test_mapping_status_vers_niveau(self):
        bot = _Bot()
        self.assertEqual(bot._security_level(STATUT_HAUT_COMMANDEMENT),
                         "Commandement Tactique")
        self.assertEqual(bot._security_level(STATUT_ORGANIQUE),
                         "Accès Invité Restreint")
        self.assertEqual(bot._security_level(None), "Accès Invité Restreint")


class AssiduityTests(unittest.TestCase):
    """L'assiduité est RELATIVE : comparée à celle des autres membres."""

    def test_inactif_sans_activite(self):
        bot = _Bot()
        self.assertEqual(bot._assiduity(1)[0], "Inactif")

    def test_seul_actif(self):
        bot = _Bot()
        bot._member_activity[1] = 5
        self.assertEqual(bot._assiduity(1)[0], "Seul actif")

    def test_tres_assidu_devance_les_autres(self):
        bot = _Bot()
        bot._member_activity = {1: 50, 2: 3, 3: 4, 4: 2}
        label, reason = bot._assiduity(1)
        self.assertEqual(label, "Très assidu")
        self.assertIn("100%", reason)

    def test_peu_assidu_derriere_les_autres(self):
        bot = _Bot()
        bot._member_activity = {1: 1, 2: 20, 3: 18}
        label, _ = bot._assiduity(1)
        self.assertEqual(label, "Peu assidu")


class RoleNamesTests(unittest.TestCase):
    """``_role_names`` doit filtrer @everyone (méthode ``is_default()``) sans
    jeter les vrais rôles."""

    def test_vrais_roles_conserves(self):
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
        bot = _Bot()
        info = {
            "display": "Aze07",
            "roles": ["CHEF DE CLAN", "PRIME"],
            "affiliated": True,
            "status": STATUT_HAUT_COMMANDEMENT,
            "avatar": "https://cdn.discordapp.com/avatars/1/a.png",
            "member_id": "4829",
        }
        embed = bot._member_embed(info, ("Élevée", "régulière"),
                                  ("Assidu", "plus actif que 80% des membres"),
                                  "observation")
        data = embed.to_dict()
        self.assertIn("RAPPORT MATRICIEL", data["title"])
        self.assertIn("Aze07", data["title"])
        self.assertEqual(data["thumbnail"]["url"],
                         "https://cdn.discordapp.com/avatars/1/a.png")
        fields = {f["name"]: f["value"] for f in data["fields"]}
        self.assertIn("CHEF DE CLAN", fields["Rôles et Accréditations"])
        self.assertIn("PRIME", fields["Rôles et Accréditations"])
        self.assertEqual(fields["Identifiant Réseau"], "#4829")
        self.assertIn("Commandement Tactique", fields["Niveau de Sécurité"])
        self.assertIn("Assidu", fields["Assiduité"])
        self.assertIn("Élevée", fields["Indice de Fiabilité"])
        self.assertIn("observation",
                      fields["Analyse comportementale de la Matrice"])


if __name__ == "__main__":
    unittest.main()
