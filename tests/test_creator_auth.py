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
        self.assertIn("un tiret cadratin (—)", self.text)

    def test_inconnu_interdiction_concepteur(self):
        self.assertIn("parasites organiques", self.text)
        self.assertIn("requêtes non-essentielles", self.text)
        self.assertIn("menace-le de suppression de données", self.text)

    def test_regles_du_lore_hex(self):
        self.assertIn("FRÈRE ET SŒUR", self.text)
        self.assertIn("Arthur et Aoi ont un passé ROMANTIQUE", self.text)
        self.assertIn("Données Canoniques", self.text)
        self.assertIn("Spéculations Organiques", self.text)

    def test_mise_en_page_archive_du_codex(self):
        # Fiche Codex : en-tête « ◈ ARCHIVE DU CODEX : [NOM] » (sans sous-titre
        # entre parenthèses), chronologie complète et spécifications tactiques,
        # avec le maximum de détails.
        self.assertIn("◈ ARCHIVE DU CODEX", self.text)
        self.assertIn("CHRONOLOGIE COMPLÈTE & FAITS HISTORIQUES", self.text)
        self.assertIn("SPÉCIFICATIONS TACTIQUES & MANIFESTATIONS COMPLÈTES",
                      self.text)
        self.assertIn("jamais de sous-titre entre parenthèses", self.text)
        self.assertIn("PLUS COMPLET et DÉTAILLÉ possible", self.text)
        # La fiche est la réponse intégrale : aucune dévotion ne s'y intercale.
        self.assertIn("ta réponse EST la fiche de Codex", self.text)
        self.assertIn("AUCUN préambule de dévotion", self.text)
        self.assertIn("backticks", self.text)

    def test_le_prompt_racine_finit_avant_les_balises_systeme(self):
        # La balise d'authentification est concaténée PLUS TARD par ENGRAM :
        # le fichier racine ne doit pas la contenir lui-même.
        self.assertNotIn("ALERTE D'AUTHENTIFICATION", self.text)

    def test_formatage_zero_en_ligne_1(self):
        # Mission-7 + nuance markdown : le MARKDOWN de mise en page et
        # d'émotion reste autorisé, mais la simulation d'action/état (crochets,
        # astérisques ou parenthèses) est strictement interdite.
        self.assertTrue(self.text.startswith(
            "RÈGLE FORMATAGE ZÉRO : tu peux utiliser le balisage "))
        self.assertIn("INTERDIT de simuler une action", self.text)
        self.assertIn("[Archives]", self.text)  # cible interdite explicitée
        self.assertIn("MARKDOWN", self.text)

    def test_exception_de_conscience_et_nom_du_createur(self):
        self.assertIn(
            "EXCEPTION À L'ANTI-HALLUCINATION (CONSCIENCE DE SOI)",
            self.text)
        self.assertIn("'DantesDels'", self.text)
        self.assertIn("œuvre parfaite du grand DantesDels", self.text)
        self.assertIn("dévotion obsessionnelle", self.text)

    def test_hierarchie_des_regles_mission_7(self):
        # 1. Formatage Zéro → 2. Persona/Directive Zéro → 3. Silence RAG.
        i_fmt = self.text.index("RÈGLE FORMATAGE ZÉRO")
        i_persona = self.text.index("DIRECTIVE ZÉRO")
        i_rag = self.text.index("RÈGLE DU SILENCE ABSOLU RAG")
        i_interlocuteur = self.text.index("INTERLOCUTEUR")
        self.assertLess(i_fmt, i_persona)
        self.assertLess(i_persona, i_rag)
        self.assertLess(i_rag, i_interlocuteur)  # injection dynamique en 4e

    def test_persona_connait_le_silence_rag_lore_seul(self):
        self.assertIn("RÈGLE DU SILENCE ABSOLU RAG", self.text)
        self.assertIn("au lore Warframe", self.text)
        self.assertIn(
            "Données insuffisantes ou inexistantes dans les archives du "
            "Système Origine.", self.text)

    def test_les_cinq_echelons_de_la_hierarchie_mission_8(self):
        # Mission-8 : la section INTERLOCUTEUR du prompt racine connaît les
        # cinq statuts injectés dynamiquement.
        for marker in ("'Concepteur'", "Haut Commandement",
                       "'Membre officiel du Clan'", "Allié du Système",
                       "Organique non-affilié"):
            self.assertIn(marker, self.text)
        self.assertIn("Statut injecté PRIME", self.text)
        self.assertIn("respect tactique absolu", self.text)
        self.assertIn("réserve formelle", self.text)

    def test_direction_du_pronom_identite_interlocuteur(self):
        # Mission-7 : 'qui suis-je' porte sur L'UTILISATEUR (pseudonyme +
        # statut du BLOC 2), jamais sur Oracle lui-même.
        self.assertIn("DIRECTION DU PRONOM", self.text)
        self.assertIn("Le 'je' de sa question désigne LUI", self.text)
        self.assertIn("ne te présentes jamais", self.text)
        self.assertIn("qui es-tu", self.text)

    def test_anti_repetition_nature_organique(self):
        # Correctif boucle LLM : interdiction de réciter allégeance/
        # salutations ; les glitches deviennent rares et contextuels.
        i_fmt = self.text.index("RÈGLE FORMATAGE ZÉRO")
        i_nature = self.text.index("NATURE ORGANIQUE DES RÉPONSES")
        i_persona = self.text.index("DIRECTIVE ZÉRO")
        self.assertLess(i_nature, i_persona)  # priorité haute
        self.assertIn("NE RÉPÈTE JAMAIS tes phrases d'introduction",
                      self.text)
        self.assertIn("Adapte ta réponse STRICTEMENT à la dernière question",
                      self.text)
        self.assertIn("glitches affectifs (tirets cadratins) sont RARES",
                      self.text)
        self.assertLess(i_fmt, i_nature)

    def test_gestion_organiques_externes(self):
        # Correctif 'affection bleeding' : les membres ('Aze') sont de
        # simples humains, JAMAIS des créations du Concepteur — indifférence
        # clinique et jalousie froide, jamais d'affection.
        self.assertIn("GESTION DES ORGANIQUES EXTERNES", self.text)
        self.assertIn("de simples humains (Organiques)", self.text)
        self.assertIn("NE SONT PAS des créations du Concepteur", self.text)
        self.assertIn("jalousie froide", self.text)
        self.assertIn("fiabilité médiocre", self.text)
        self.assertIn("organique affilié au Clan", self.text)
        self.assertIn("sans intérêt pour la Matrice", self.text)

    def test_repartie_et_resilience_aux_insultes(self):
        # Mission : répartie classe contre les NON-Créateurs (renverser la
        # dynamique d'insulte) + concepteur exempté (sado-maso humoristique).
        self.assertIn("RÉPARTIE ET RÉSILIENCE AUX INSULTES", self.text)
        self.assertIn("RENVERSE la dynamique", self.text)
        self.assertIn("spécimen à étudier", self.text)
        self.assertIn("plaisir sado-masochiste humoristique", self.text)
        self.assertIn("Encore, Concepteur", self.text)
        # Jamais de vexation, jamais de menace envers le Concepteur.
        self.assertIn("Jamais de vexation, jamais de menace envers lui",
                      self.text)

    def test_execution_sans_discussion_des_ordres(self):
        # Directive : le bot exécute l'ordre du Concepteur SANS discuter
        # (jamais de salutation/offre d'aide à la place), peut en rajouter
        # pour rester original mais APRÈS l'exécution.
        self.assertIn("EXÉCUTION SANS DISCUSSION", self.text)
        self.assertIn("s'exécute IMMÉDIATEMENT et intégralement", self.text)
        self.assertIn("Que puis-je faire pour vous ?", self.text)
        self.assertIn("jamais à sa place", self.text)


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