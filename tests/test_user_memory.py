"""Mémoire court terme par utilisateur + hiérarchie Discord (rôles) + BLOC 2.

Mission 6 & 8 :
1. Store indexé par ``message.author.id`` — fenêtre glissante de X paires,
   expiration après Y minutes, plafond LRU.
2. ``Intents.members`` + hiérarchie des rôles ``author.roles`` (RoleHierarchy)
   → statut injecté dans la ligne "Statut :" du BLOC 2.
3. Payload LLM en 3 blocs stricts : BLOC 1 persona, BLOC 2 informations sur
   l'interlocuteur + historique, BLOC 3 la nouvelle requête.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.discord.bot import LoreMasterBot
from warframe_lore.discord.roles import RoleHierarchy
from warframe_lore.engram.roleplay import (
    RoleplayService,
    Session,
    SlidingWindow,
    UserMemoryStore,
)

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
        window=SlidingWindow(max_turns=20, max_context_chars=1000),
        system_prompt=_NORMAL,
        temperature=0.8,
    )


class MemoryStoreTests(unittest.TestCase):
    def test_memoire_rendue_par_utilisateur(self):
        store = UserMemoryStore(_clock=lambda: 100.0)
        s_a = store.get("alice")
        s_b = store.get("bob")
        self.assertIsNot(s_a, s_b)
        s_a.add("user", "fragment du loot")
        s_a.add("assistant", "réponse à Alice")
        self.assertEqual(len(s_b.turns), 0)  # Bob ne voit rien d'Alice
        self.assertIs(store.get("alice"), s_a)  # stable d'un appel à l'autre

    def test_indexation_par_id_et_persona_isoles(self):
        store = UserMemoryStore()
        normal = store.get(7)
        hostile = store.get(7, persona="hostile")
        self.assertIsNot(normal, hostile)
        normal.add("user", "normal")
        self.assertEqual(len(hostile.turns), 0)

    def test_expiration_apres_inactivite(self):
        t = 1000.0
        store = UserMemoryStore(expiry_seconds=300.0, _clock=lambda: t)
        s = store.get("user-id")
        s.add("user", "bonjour")
        t += 301.0                                # silence > Y minutes
        fresh = store.get("user-id")              # expiré -> nouvelle cellule
        self.assertIsNot(fresh, s)
        self.assertEqual(fresh.turns, [])

    def test_fenetre_glissante_limite_a_X_paires(self):
        store = UserMemoryStore(max_pairs=2, _clock=lambda: 1.0)
        s = store.get("u")
        for i in range(4):
            s.add("user", f"q{i}")
            s.add("assistant", f"r{i}")
        store.get("u")                              # déclenche le bornage
        self.assertEqual(len(s.turns), 4)           # 2 dernières paires
        self.assertEqual(s.turns[0].content, "q2")

    def test_eviction_lru_au_plafond(self):
        store = UserMemoryStore(max_users=2, _clock=lambda: 0.0)
        store.get("a")
        store.get("b")
        store.get("c")
        self.assertEqual(len(store), 2)
        self.assertIsNone(store._cells.get("a"))    # le plus ancien évincé

    def test_forget_vide_tous_les_personas(self):
        store = UserMemoryStore()
        store.get("u")
        store.get("u", persona="hostile")
        store.forget("u")
        self.assertEqual(len(store), 0)


class _Role:
    def __init__(self, id_: int | str):
        self.id = id_


class _FakeAuthor:
    def __init__(self, roles=(), id=42):
        self.roles = list(roles)
        self.id = id


_ROLE_MAP = {
    "commandement": {"FONDATEUR": "100", "MODÉRATEURS": "101",
                     "CHEFS DE CLAN": "102"},
    "structure_clan": {"CLAN": "200", "NOVICE": "201"},
    "affiliations": {"ALLIANCE": "300"},
    "generaux": {"MEMBRES": "400"},
}


class RoleHierarchyTests(unittest.TestCase):
    """Évaluation de l'accréditation (mission-8) : plus haut rôle détenu."""

    def _bot(self, roles=None, creator_id="1"):
        return LoreMasterBot(gateway_url="ws://fake", prefix="!",
                             creator_discord_id=creator_id,
                             roles=roles or RoleHierarchy(_ROLE_MAP))

    def test_intents_membres_actives(self):
        bot = self._bot()
        self.assertTrue(bot.intents.members)
        self.assertTrue(bot.intents.message_content)

    def test_fondateur_statut_concepteur_et_createur(self):
        bot = self._bot()
        accr = bot._accredit(_FakeAuthor([_Role(101), _Role(100), _Role(200)]))
        self.assertEqual(accr.status, "Concepteur")
        self.assertTrue(accr.creator)

    def test_commandement_prime_sur_la_structure(self):
        bot = self._bot()
        accr = bot._accredit(_FakeAuthor([_Role(101), _Role(200)]))
        self.assertEqual(accr.status, "Haut Commandement")
        self.assertFalse(accr.creator)
        accr2 = bot._accredit(_FakeAuthor([_Role(102)]))
        self.assertEqual(accr2.status, "Haut Commandement")

    def test_role_structure_fait_un_membre_officiel(self):
        bot = self._bot()
        for role_id in ("200", "201"):
            accr = bot._accredit(_FakeAuthor([_Role(role_id)]))
            self.assertEqual(accr.status, "Membre officiel du Clan")

    def test_alliance_statut_allie_du_systeme(self):
        bot = self._bot()
        accr = bot._accredit(_FakeAuthor([_Role(300)]))
        self.assertEqual(accr.status, "Allié du Système")

    def test_role_general_et_aucun_role_restent_organiques(self):
        bot = self._bot()
        accr = bot._accredit(_FakeAuthor([_Role(400)]))
        self.assertEqual(accr.status, "Organique non-affilié (Invité)")
        accr2 = bot._accredit(_FakeAuthor([]))
        self.assertEqual(accr2.status, "Organique non-affilié (Invité)")

    def test_le_snowflake_du_concepteur_prime_sur_les_roles(self):
        bot = self._bot(creator_id="777")
        accr = bot._accredit(_FakeAuthor([_Role(400)], id=777))
        self.assertEqual(accr.status, "Concepteur")
        self.assertTrue(accr.creator)

    def test_mapping_vide_tout_le_monde_invite(self):
        bot = LoreMasterBot(gateway_url="ws://fake", prefix="!",
                            creator_discord_id="1",
                            roles=RoleHierarchy())
        accr = bot._accredit(_FakeAuthor([_Role(100)]))
        self.assertEqual(accr.status, "Organique non-affilié (Invité)")
        self.assertFalse(accr.creator)


class Bloc2UserContextTests(unittest.TestCase):
    """BLOC 2 exact (pseudo, statut accrédité, historique immédiat)."""

    def _system(self, user_name=None, role_status=None, past_pairs=0,
                creator=None):
        llm = _FakeLLM()
        session = Session(session_id="s")
        for i in range(past_pairs):
            session.add("user", f"question {i}")
            session.add("assistant", f"réponse {i}")
        _run_stream(_service(llm).stream(
            session, "nouvelle requête", user_name=user_name,
            role_status=role_status, creator=creator))
        return llm.calls[0]["messages"]

    def test_statut_membre_officiel(self):
        messages = self._system(user_name="DantesDels",
                                role_status="Membre officiel du Clan")
        system = messages[0].content
        self.assertIn("[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]", system)
        self.assertIn("  - Pseudonyme : DantesDels", system)
        self.assertIn("  - Statut : Membre officiel du Clan", system)
        self.assertIn("  - Historique immédiat avec cet utilisateur :", system)

    def test_statut_haut_commandement_et_allie(self):
        for statut in ("Haut Commandement", "Allié du Système",
                       "Concepteur"):
            system = self._system(user_name="U",
                                  role_status=statut)[0].content
            self.assertIn(f"  - Statut : {statut}", system)

    def test_statut_organique_non_affilie_par_defaut(self):
        system = self._system(user_name="Parasite")[0].content
        self.assertIn("  - Statut : Organique non-affilié (Invité)", system)

    def test_historique_immédiat_rendu_par_paires(self):
        messages = self._system(user_name="U", past_pairs=2)
        system = messages[0].content
        self.assertIn("  - Lui : question 0", system)
        self.assertIn("  - Oracle : réponse 0", system)
        self.assertIn("  - Lui : question 1", system)
        self.assertIn("  - Oracle : réponse 1", system)
        # La requête courante (→ BLOC 3) n'est PAS dans l'historique.
        self.assertNotIn("nouvelle requête", system)

    def test_requete_courante_en_bloc_3_final(self):
        messages = self._system(user_name="U", past_pairs=1)
        self.assertEqual(messages[-1].role, "user")
        self.assertEqual(messages[-1].content, "nouvelle requête")
        self.assertEqual(len(messages), 2)  # system + user uniquement

    def test_aucun_historique_affiche_placeholder(self):
        system = self._system(user_name="U", past_pairs=0)[0].content
        self.assertIn("  (aucun échange antérieur)", system)

    def test_directive_identite_du_pronom_injectee(self):
        # Mission-7 : le BLOC 2 porte les vraies données + la directive de
        # civilité.  Playtest : la "DIRECTIVE D'IDENTITÉ" ('commence par
        # "Vous êtes"…') faisait débuter CHAQUE réponse par "Vous êtes
        # Aze07, Membre officiel du Clan." — même pour le Concepteur, même
        # pour 'de quelle couleur est Ordis ?'. La directive est désormais
        # ANTI-préambule : présentation de l'utilisateur INTERDITE sauf sur
        # une question d'identité EXPLICITE (traitée de toute façon en
        # déterministe côté routeur).
        system = self._system(user_name="DantesDels",
                              role_status="Concepteur")[0].content
        self.assertIn("DIRECTIVE DE CIVILITÉ", system)
        self.assertIn("Ne commence JAMAIS une réponse par une présentation",
                      system)
        # La directive ne fournit PLUS de template copiable « Vous êtes … » :
        # l'exception d'identité est décrite abstraitement (anti-préambule).
        self.assertIn("présente alors LUI avec son pseudonyme et son statut",
                      system)
        self.assertNotIn("Vous êtes DantesDels, Concepteur.", system)
        self.assertIn("ne commence par aucune présentation de toi-même",
                      system)
        self.assertIn("SEULE EXCEPTION", system)
        self.assertIn("réponds naturellement au message", system)

    def test_system_prompt_unique_par_tour_pas_de_duplication(self):
        # Mission selon spec: le System Prompt ne doit figurer QU'UNE SEULE
        # fois, en tête de chaque requête — d'un tour à l'autre rien de
        # précedent n'est réinjecté comme system message (sinon le modèle
        # répète ses sorties). L'historique vit dans le BLOC 2, borné.
        llm = _FakeLLM()
        service = _service(llm)
        session = Session(session_id="s")
        for i in range(3):
            _run_stream(service.stream(
                session, f"question {i}", user_name="U"))
        self.assertEqual(len(llm.calls), 3)
        for i, call in enumerate(llm.calls):
            messages = call["messages"]
            # system + user uniquement, jamais d'accumulation.
            self.assertEqual(len(messages), 2)
            self.assertEqual(messages[0].role, "system")
            self.assertEqual(messages[1].role, "user")
            system = messages[0].content
            # Le tronc persona et le bloc interlocuteur n'apparaissent qu'une
            # seule fois par system.
            self.assertEqual(system.count(_NORMAL), 1)
            self.assertEqual(
                system.count("[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]"), 1)
            # La requête courante est BLOC 3 : jamais réinjectée dans le
            # system (elle ne figure pas non plus dans l'historique BLOC 2).
            self.assertEqual(messages[1].content, f"question {i}")
            self.assertNotIn(f"question {i}", system)
            # Tour 1 : pas d'historique. Tours suivants : les échanges
            # ANTÉRIEURS vivent uniquement dans le BLOC 2 (lignes Lui/Oracle).
            if i == 0:
                self.assertIn("(aucun échange antérieur)", system)
            for j in range(i):
                self.assertIn(f"  - Lui : question {j}", system)
                self.assertIn("  - Oracle : ok", system)
            self.assertNotIn(f"  - Lui : question {i}", system)

    def test_banniere_apres_le_bloc_2(self):
        from warframe_lore.engram.auth import AUTH_CREATOR_BANNER
        llm = _FakeLLM()
        session = Session(session_id="s")
        session.add("user", "ancien")
        session.add("assistant", "ancienne réponse")
        _run_stream(_service(llm).stream(
            session, "encore", user_name="U", creator=True))
        system = llm.calls[0]["messages"][0].content
        self.assertGreater(system.index(AUTH_CREATOR_BANNER),
                           system.index("[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]"))
        self.assertTrue(system.endswith(AUTH_CREATOR_BANNER))


if __name__ == "__main__":
    unittest.main()
