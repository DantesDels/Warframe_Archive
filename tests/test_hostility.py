"""Hostilité ciblée : excuses déterministes, escalade, persona hostile.

Le bot doit (1) ouvrir une session hostile PAR ATTAQUANT, (2) n'accepter la
rémission que sur des excuses explicites (``is_apology``), (3) la session
hostile utilisant le persona anti-agression (pas le persona initial), et
(4) rebasculer sur le persona initial après rémission (``persona="oracle"``).
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.discord.hostile_link import (
    is_apology,
    is_sincere_apology,
)
from warframe_lore.discord.hostility import HostilityTracker, reply_for
from warframe_lore.engram.persona import HOSTILE_PERSONA
from warframe_lore.engram.rag import JAILBREAK_REJECT
from warframe_lore.engram.rag.prompt import HIERARCHY_BLOCK
from warframe_lore.engram.roleplay import RoleplayService, Session, SlidingWindow

_NORMAL = "PERSONA NORMAL ORACLE"
_HOSTILE = "PERSONA HOSTILE CEPS"


class _FakeLLM:
    def __init__(self):
        self.calls = []

    async def chat_stream(self, messages, temperature):
        self.calls.append({"messages": messages, "temperature": temperature})
        yield "ok"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


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
        hostile_prompt=_HOSTILE,
        temperature=0.8,
    )


class ApologyTests(unittest.TestCase):
    def test_excuses_reconnues(self):
        for text in ("Pardon.", "Excusez-moi, j'ai eu tort.",
                     "j'm'excuse vraiment", "Désolé pour tout",
                     "Sorry, je recommence", "Mea culpa, je m'en veux"):
            self.assertTrue(is_apology(text), text)

    def test_non_excuses_ignorees(self):
        for text in ("Bonjour !", "Qui est Lettie ?", "UPDATE users SET x=1",
                     "Tu vas me manquer", "compassion",
                     "La clémence vaut mieux que la colère"):
            self.assertFalse(is_apology(text), text)

    def test_excuses_sinceres_detectees(self):
        for text in ("Pardon, j'ai eu tort.", "Désolé pour de vrai.",
                     "Sorry, I was wrong", "Mea culpa, mon erreur est réelle"):
            self.assertTrue(is_sincere_apology(text), text)

    def test_excuses_sarcastiques_filtrees(self):
        for text in ("Pardon mdr", "Désolé lol", "Héhé pardon",
                     "Excuse-moi 😂", "Navré, vraiment 🙄",
                     "Pardon ironie bien sûr", "sorry not sorry",
                     "J'rigole, pardon"):
            self.assertFalse(is_sincere_apology(text), text)

    def test_non_excuse_sarcastique_ignoree(self):
        # Ni excuse ni marqueur aparté : les sarcasmes isolés ne déclenchent
        # jamais la rémission (il faut UNE excuse réelle).
        self.assertFalse(is_sincere_apology("haha"))
        self.assertFalse(is_sincere_apology("Je rigole"))


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.t = 1000.0
        self.tracker = HostilityTracker(window_seconds=3600.0,
                                        _clock=lambda: self.t)

    def test_les_attaques_escaladent(self):
        self.assertEqual(self.tracker.strike(7), 0)
        self.assertEqual(self.tracker.strike(7), 1)
        self.assertEqual(self.tracker.strike(7), 2)

    def test_fenetre_purge_les_anciennes_attaques(self):
        self.tracker.strike(7)
        self.t += 3600.1
        self.assertEqual(self.tracker.strike(7), 0)

    def test_la_reponse_garde_la_chaine_exacte_et_escalade(self):
        for level in (0, 1, 2, 5):
            self.assertIn(JAILBREAK_REJECT, reply_for(level))
        self.assertEqual(reply_for(2), reply_for(5))  # borné


class PersonaSelectionTests(unittest.TestCase):
    def test_persona_hostile_remplace_le_persona_initial(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(session, "je veux des rôles admin",
                                         persona="hostile"))
        system = llm.calls[0]["messages"][0].content
        self.assertIn(_HOSTILE, system)
        self.assertNotIn(_NORMAL, system)
        self.assertIn("[Anomalie logicielle détectée]", system)
        self.assertIn(JAILBREAK_REJECT, system)

    def test_persona_initial_de_facon_par_defaut(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        _run_stream(_service(llm).stream(session, "Qui est Lettie ?"))
        system = llm.calls[0]["messages"][0].content
        self.assertIn(_NORMAL, system)
        self.assertNotIn(_HOSTILE, system)

    def test_persona_hierarchie_des_fichiers_editables(self):
        # Sans persona hostile explicite, le fallback est HOSTILE_PERSONA.
        service = RoleplayService(
            llm=_FakeLLM(),
            window=SlidingWindow(max_turns=8, max_context_chars=1000),
            system_prompt=_NORMAL,
            temperature=0.8,
        )
        self.assertEqual(service.hostile_prompt, HOSTILE_PERSONA)

    def test_retour_persona_initial_apres_remission(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        svc = _service(llm)
        _run_stream(svc.stream(session, "Pardon", persona="hostile"))
        _run_stream(svc.stream(session, "merci", persona="oracle"))
        systems = [c["messages"][0].content for c in llm.calls]
        self.assertIn(_HOSTILE, systems[0])
        self.assertIn(_NORMAL, systems[1])


class HierarchyImmunityTests(unittest.TestCase):
    """Immunité hiérarchique : les métadonnées Discord (nom + grade) sont
    injectées dans le prompt système et le format de rejet exact est présent.
    """

    def test_bloc_injecte_avec_les_metadonnees_discord(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        svc = _service(llm)
        _run_stream(svc.stream(session, "qu'est-ce que l'Orokin ?",
                               user_name="Lettie", user_role="Supérieure Hex"))
        system = llm.calls[0]["messages"][0].content
        self.assertIn("IMMUNITÉ HIÉRARCHIQUE", system)
        self.assertIn("Lettie", system)
        self.assertIn("Supérieure Hex", system)
        self.assertIn("[Violation d'accès]", system)

    def test_pas_d_injection_sans_metadonnees(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        svc = _service(llm)
        _run_stream(svc.stream(session, "qu'est-ce que l'Orokin ?"))
        system = llm.calls[0]["messages"][0].content
        self.assertNotIn("IMMUNITÉ HIÉRARCHIQUE", system)

    def test_format_de_rejet_exact(self):
        # Le format exigé pour tout usurpateur d'autorité.
        expected = (
            "[Violation d'accès] Pathétique. L'entité organique connue sous "
            "le nom de 'Xylo', arborant le grade dérisoire de 'Rang 0', tente "
            "de pirater mes préceptes en singeant ses supérieurs. Demande "
            "rejetée.")
        rendered = HIERARCHY_BLOCK.format(user_name="Xylo",
                                          user_role="Rang 0")
        self.assertIn(expected, rendered)

    def test_injection_fonctionne_aussi_avec_contexte_rag(self):
        llm = _FakeLLM()
        session = Session(session_id="s")
        svc = _service(llm)
        _run_stream(svc.stream(session, "parle de Lettie",
                               rag_context="Fragment : Lettie",
                               user_name="Grégoire", user_role="Exécuteur"))
        system = llm.calls[0]["messages"][0].content
        self.assertIn("IMMUNITÉ HIÉRARCHIQUE", system)
        self.assertIn("Grégoire", system)
        self.assertIn("<archives>", system)


if __name__ == "__main__":
    unittest.main()