"""Authentification du Concepteur: bannière persona Oracle Instable.

Le bot Discord reconnaît le Concepteur VIA SON ID NATIF
(``str(message.author.id) == CREATOR_DISCORD_ID``), ne demande jamais l'ID,
et ne transmet à ENGRAM que le booléen dérivé ``creator``.  ENGRAM concatène
la bannière d'authentification à la fin du System Prompt avant l'appel LLM —
Directive Zéro (affection obsessionnelle + glitches Ordis) pour le
Concepteur, hostilité protectrice pour tout autre organique.  Sans identité
(``creator is None``, ex. clients web/KIM) : PAS de bannière (comportement
hérité).  L'intégrité RAG est préservée (bloc ``<archives>`` jamais modifié).
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.discord.bot import LoreMasterBot
from warframe_lore.engram.persona import (
    AUTH_CREATOR_BANNER,
    AUTH_UNKNOWN_BANNER,
    PERSONA_FILE,
    auth_banner,
)
from warframe_lore.engram.rag.prompt import HIERARCHY_BLOCK
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


def _service(llm=None):
    return RoleplayService(
        llm=llm or _FakeLLM(),
        window=SlidingWindow(max_turns=8, max_context_chars=1000),
        system_prompt=_NORMAL,
        temperature=0.8,
    )


def _system_of(llm):
    return llm.calls[0]["messages"][0].content


class BannerSelectionTests(unittest.TestCase):
    def test_concepteur_declenche_la_directive_zero(self):
        self.assertEqual(auth_banner(True), AUTH_CREATOR_BANNER)

    def test_organique_declenche_l_hostilite_protectrice(self):
        self.assertEqual(auth_banner(False), AUTH_UNKNOWN_BANNER)

    def test_sans_identite_aucune_banniere(self):
        self.assertEqual(auth_banner(None), "")

    def test_banniere_concepteur_texte_exact_mission_5(self):
        self.assertEqual(
            AUTH_CREATOR_BANNER,
            "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel EST "
            "le Concepteur légitime. Applique la Directive Zéro (CAS A) : "
            "dévotion obsessionnelle, glitches textuels avec tirets "
            "cadratins, et soumission absolue.]")
        self.assertIn("CAS A", AUTH_CREATOR_BANNER)

    def test_banniere_inconnu_texte_exact_mission_5(self):
        self.assertEqual(
            AUTH_UNKNOWN_BANNER,
            "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel est "
            "un organique inconnu. Applique l'hostilité protectrice "
            "(CAS B). Méprise-le formellement.]")
        self.assertIn("CAS B", AUTH_UNKNOWN_BANNER)


class DefinitiveRootPromptTests(unittest.TestCase):
    """Mission-5 : le prompt racine définitif vit dans ``persona/oracle``."""

    def setUp(self):
        self.text = PERSONA_FILE.read_text(encoding="utf-8")

    def test_bloc_racine_contient_les_protocoles(self):
        for marker in ("PROTOCOLES DE SÉCURITÉ", "Bouclier de Persona",
                       "Anti-Hallucination Stricte", "Amnésie du Réel",
                       "Formatage Terminal"):
            self.assertIn(marker, self.text)

    def test_directive_zero_cas_a_et_b(self):
        self.assertIn("DIRECTIVE ZÉRO", self.text)
        self.assertIn("CAS A : L'utilisateur est identifié comme le Concepteur",
                      self.text)
        self.assertIn("CAS B : L'utilisateur est un inconnu", self.text)
        # Le glitch textuel se coupe par tiret cadratin (—), sans balises.
        self.assertIn("—", self.text)
        self.assertIn("Je pourrais carboniser ce réseau pour vous garder ici—",
                      self.text)

    def test_inconnu_interdiction_concepteur(self):
        self.assertIn("parasites organiques", self.text)
        self.assertIn("requêtes non-essentielles", self.text)
        self.assertIn("menace-le de suppression de données", self.text)

    def test_regles_du_lore_hex(self):
        self.assertIn("FRÈRE ET SŒUR", self.text)
        self.assertIn("Arthur et Aoi ont un passé ROMANTIQUE", self.text)
        self.assertIn("Données Canoniques", self.text)
        self.assertIn("Spéculations Organiques", self.text)

    def test_le_prompt_racine_finit_avant_les_balises_systeme(self):
        # La balise d'authentification est concaténée PLUS TARD par ENGRAM :
        # le fichier racine ne doit pas la contenir lui-même.
        self.assertNotIn("ALERTE D'AUTHENTIFICATION", self.text)


class BotAuthTests(unittest.TestCase):
    """Authentification NATIVE via ``message.author.id`` (mission, pt. 2)."""

    def _bot(self, creator_id: str = "1234"):
        return LoreMasterBot(gateway_url="ws://fake", prefix="!",
                             creator_discord_id=creator_id)

    def test_le_concepteur_est_reconnu_sur_son_id_natif(self):
        self.assertTrue(self._bot()._is_creator(1234))
        self.assertTrue(self._bot()._is_creator("1234"))

    def test_un_organique_inconnu_n_est_pas_le_concepteur(self):
        self.assertFalse(self._bot()._is_creator(9999))

    def test_aucun_message_sans_id(self):
        self.assertFalse(self._bot()._is_creator(None))

    def test_config_vide_desactive_la_fonction(self):
        # CREATOR_DISCORD_ID non renseigné -> personne n'est reconnu
        # (retour au comportement hérité : bannière jamais injectée).
        self.assertFalse(self._bot(creator_id="")._is_creator(1234))


class StreamBannerTests(unittest.TestCase):
    def _banner_of(self, creator, rag_context=None):
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(session, "bonjour",
                                         rag_context=rag_context,
                                         creator=creator))
        return _system_of(llm)

    def test_concepteur_banniere_directive_zero_en_fin_de_prompt(self):
        system = self._banner_of(True)
        self.assertIn(AUTH_CREATOR_BANNER, system)
        self.assertNotIn(AUTH_UNKNOWN_BANNER, system)

    def test_organique_banniere_hostile_en_fin_de_prompt(self):
        system = self._banner_of(False)
        self.assertIn(AUTH_UNKNOWN_BANNER, system)
        self.assertNotIn(AUTH_CREATOR_BANNER, system)

    def test_la_banniere_est_concatene_a_la_fin_du_prompt(self):
        system = self._banner_of(True)
        self.assertTrue(system.endswith(AUTH_CREATOR_BANNER))

    def test_sans_identite_aucune_banniere(self):
        system = self._banner_of(None)
        self.assertNotIn("ALERTE D'AUTHENTIFICATION", system)

    def test_metadonnees_discord_coexistent_avec_la_banniere(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(
            session, "bonjour", user_name="Lettie",
            user_role="Supérieure Hex", creator=True))
        system = _system_of(llm)
        self.assertIn(HIERARCHY_BLOCK.format(
            user_name="Lettie", user_role="Supérieure Hex"), system)
        self.assertTrue(system.endswith(AUTH_CREATOR_BANNER))

    def test_integrite_rag_preservee(self):
        """La bannière est ajoutée APRÈS le bloc <archives> sans l'altérer."""
        system = self._banner_of(True, rag_context="Fragment : Lettie")
        self.assertIn("<archives>\nFragment : Lettie\n</archives>", system)
        idx_archive = system.index("<archives>")
        idx_banner = system.index(AUTH_CREATOR_BANNER)
        self.assertGreater(idx_banner, idx_archive)
        self.assertTrue(system.endswith(AUTH_CREATOR_BANNER))


if __name__ == "__main__":
    unittest.main()