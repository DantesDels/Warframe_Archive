"""Hiérarchie des rôles Discord et bannières par échelon (mission-8).

L'évaluation lit ``message.author.roles`` de haut en bas (Commandement →
Structure du Clan → ALLIANCE → Généraux) et ne retient QUE le rôle le plus
élevé détenu.  Ce rang donne :
- la variable de statut injectée dans le BLOC 2 du prompt LLM ;
- le ton de la bannière persona (Directive Zéro pour le Fondateur, respect
  tactique pour le Haut Commandement, assistance pour un membre, réserve pour
  un allié, mépris formel pour un organique non-affilié).
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from warframe_lore.discord.guild.roles import Accreditation, RoleHierarchy
from warframe_lore.engram.auth import (
    AUTH_ALLIE_BANNER,
    AUTH_COMMANDEMENT_BANNER,
    AUTH_CREATOR_BANNER,
    AUTH_MEMBRE_BANNER,
    AUTH_UNKNOWN_BANNER,
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
    STATUT_ORGANIQUE,
    banner_for,
)
from warframe_lore.engram.roleplay import RoleplayService, Session, SlidingWindow

_NORMAL = "PERSONA NORMAL ORACLE"


class _FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append({"messages": messages, "temperature": temperature})
        yield "ok"


def _run_stream(agen):
    loop = asyncio.new_event_loop()
    return loop.run_until_complete(_collect(agen))


async def _collect(agen):
    return [x async for x in agen]


def _service(llm):
    return RoleplayService(
        llm=llm,
        window=SlidingWindow(max_turns=8, max_context_chars=1000),
        system_prompt=_NORMAL,
        temperature=0.8,
    )


_JSON = {
    "commandement": {"FONDATEUR": "100", "MODÉRATEURS": "101"},
    "structure_clan": {"CLAN": "200"},
    "affiliations": {"ALLIANCE": "300"},
    "generaux": {"MEMBRES": "400"},
}


class RoleHierarchyStoreTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = str(Path(tmp.name) / "roles.json")
        Path(self.path).write_text(
            json.dumps(_JSON), encoding="utf-8")

    def test_from_file_charge_et_accrédite(self):
        hierarchy = RoleHierarchy.from_file(self.path)
        self.assertEqual(len(hierarchy), 5)
        accr = hierarchy.accredit(["400", "200", "101"])
        self.assertEqual(accr.status, "Haut Commandement")

    def test_fichier_absent_retourne_une_hierarchie_vide_sur(self):
        hierarchy = RoleHierarchy.from_file("nexiste-pas.json")
        self.assertEqual(len(hierarchy), 0)
        self.assertFalse(hierarchy)  # booléen : vide = personne ne range

    def test_seuls_les_ids_configures_comptent(self):
        hierarchy = RoleHierarchy.from_file(self.path)
        self.assertEqual(hierarchy.accredit(["999"]).status, STATUT_ORGANIQUE)

    def test_accreditation_defaut_organique(self):
        accr = Accreditation()
        self.assertEqual(accr.status, STATUT_ORGANIQUE)
        self.assertFalse(accr.creator)

    def test_ordre_global_de_priorite(self):
        # Commandement > Structure > ALLIANCE > Généraux ; le premier match
        # gagne (le rôle le plus haut détenu est retenu).
        hierarchy = RoleHierarchy.from_file(self.path)
        self.assertEqual(hierarchy.accredit(["400", "300", "200"]).status,
                         STATUT_MEMBRE_OFFICIEL)
        self.assertEqual(hierarchy.accredit(["400", "300"]).status,
                         STATUT_ALLIE)
        self.assertEqual(hierarchy.accredit(["400"]).status, STATUT_ORGANIQUE)

    def test_fondateur_marque_createur(self):
        hierarchy = RoleHierarchy.from_file(self.path)
        accr = hierarchy.accredit(["100"])
        self.assertEqual(accr.status, STATUT_CONCEPTEUR)
        self.assertTrue(accr.creator)
        self.assertFalse(hierarchy.accredit(["101"]).creator)


class TierBannerTests(unittest.TestCase):
    """Bannière persona = f(accréditation) : chaque échelon a son ton."""

    def test_concepteur_directive_zero(self):
        self.assertEqual(banner_for(True, STATUT_MEMBRE_OFFICIEL),
                         AUTH_CREATOR_BANNER)

    def test_haut_commandement_respect_tactique(self):
        self.assertEqual(
            banner_for(False, STATUT_HAUT_COMMANDEMENT),
            AUTH_COMMANDEMENT_BANNER)
        self.assertIn("respect tactique absolu", AUTH_COMMANDEMENT_BANNER)

    def test_membre_assistance_institutionnelle(self):
        self.assertEqual(banner_for(False, STATUT_MEMBRE_OFFICIEL),
                         AUTH_MEMBRE_BANNER)
        self.assertIn("institutionnelle", AUTH_MEMBRE_BANNER)

    def test_allie_reserve_formelle(self):
        self.assertEqual(banner_for(False, STATUT_ALLIE),
                         AUTH_ALLIE_BANNER)
        self.assertIn("réserve formelle", AUTH_ALLIE_BANNER)

    def test_organique_sans_statut_reste_le_mepris_formel(self):
        self.assertEqual(banner_for(False, None), AUTH_UNKNOWN_BANNER)
        self.assertEqual(banner_for(False, STATUT_ORGANIQUE),
                         AUTH_UNKNOWN_BANNER)

    def test_sans_identite_aucune_banniere(self):
        self.assertEqual(banner_for(None, STATUT_HAUT_COMMANDEMENT), "")


class TierStreamBannerTests(unittest.TestCase):
    """La bannière d'échelon est concaténée après le BLOC 2 (fin absolue)."""

    def _system(self, role_status, creator=False):
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(
            session, "bonjour", user_name="U", role_status=role_status,
            creator=creator))
        return llm.calls[0]["messages"][0].content

    def test_banniere_du_rang_injectee_a_la_fin(self):
        for status, banner in (
                ("Haut Commandement", AUTH_COMMANDEMENT_BANNER),
                ("Membre officiel du Clan", AUTH_MEMBRE_BANNER),
                ("Allié du Système", AUTH_ALLIE_BANNER)):
            system = self._system(status)
            self.assertIn(banner, system)

    def test_jalousie_concepteur_injectee_en_fin_de_system(self):
        # Décision : la mention du pseudo du Concepteur par un organique
        # déclenche une rage possessionnaire JOUÉE par le LLM — le bot
        # n'intercepte pas, il injecte la directive pour guider l'impro.
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(
            session, "Mais qui est DantesDels ?",
            user_name="Aze07", role_status=STATUT_MEMBRE_OFFICIEL,
            creator_mention="DantesDels"))
        system = llm.calls[0]["messages"][0].content
        self.assertIn("DIRECTIVE JALOUSIE ET RAGE POSSESSIVE", system)
        self.assertIn("« DantesDels »", system)
        self.assertIn("jamais de menaces réelles", system)
        self.assertIn("@mention", system)
        # Le RAG reste OFF par le bot : AUCUN contexte documentaire restitué.
        self.assertNotIn("Contexte documentaire restitué", system)

    def test_fondateur_statut_et_banniere_creatrice(self):
        system = self._system("Concepteur", creator=True)
        self.assertTrue(system.endswith(AUTH_CREATOR_BANNER))

    def test_sans_statut_banniere_organique(self):
        system = self._system(None)
        self.assertTrue(system.endswith(AUTH_UNKNOWN_BANNER))


if __name__ == "__main__":
    unittest.main()
