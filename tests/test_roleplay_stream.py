"""Émission WS d'un tour Roleplay : les jetons, puis la trame ``end``.

Le contrat partagé porte la pagination narrative sur la trame terminale : le
bot y apprend s'il reste des fragments du dossier derrière le curseur qu'il a
envoyé (``story_more``), seule information qui autorise l'enchaînement d'une
partie supplémentaire.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.engram.api.routers.roleplay_stream import (
    STORY_RETRY_LIMIT,
    collapse_repeated_closing,
    emit_story_turn,
    emit_stream,
)
from warframe_lore.engram.rag import JAILBREAK_REJECT, RAG_ERROR, RAGContext
from warframe_lore.engram.roleplay import Session
from warframe_lore.engram.roleplay.prompt import (
    STORY_COMPLETE_SENTENCE,
    STORY_PAGINATION_SENTENCE,
)
from warframe_lore.engram.roleplay.purge import canonical_story_closing

TOKENS = ("Ballas fut le ", "Conseiller ", "des Orokin.")

# A continuation frame of a running tale: ``text`` is the bot's canned
# "continue", ``retrieval_text`` the request that anchored the story.
STORY_PAYLOAD = {
    "type": "message",
    "text": "Poursuis le récit.",
    "rag": True,
    "story": True,
    "story_lens": None,
    "targeted_era": "l'Ère Orokin",
    "targeted_subject": "albrecht",
    "leverian_warframe": None,
    "retrieval_text": "raconte l'histoire d'Albrecht",
    "dossier_offset": 1,
    "user_id": "curiosité",
    "user_name": "Mira",
    "user_role": "chancre",
    "role_status": "organique",
    "creator": False,
    "creator_mention": None,
    "lang": "fr",
}


async def tokens():
    for token in TOKENS:
        yield token


def run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeWebSocket:
    """Enregistre les trames JSON émises (aucun réseau)."""

    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.frames.append(payload)


class EmitStreamTests(unittest.TestCase):
    def test_la_trame_finale_annonce_la_suite_du_dossier(self):
        socket = FakeWebSocket()
        run(emit_stream(socket, tokens(), story_more=True))
        self.assertEqual([f["type"] for f in socket.frames],
                         ["token", "token", "token", "end"])
        self.assertEqual(socket.frames[-1]["text"], "".join(TOKENS))
        self.assertTrue(socket.frames[-1]["story_more"])

    def test_un_dossier_epuise_ne_promet_aucune_suite(self):
        socket = FakeWebSocket()
        run(emit_stream(socket, tokens()))
        self.assertFalse(socket.frames[-1]["story_more"])

    def test_un_doublon_de_l_invitation_en_queue_est_fusionne(self):
        # Le modèle a collé la phrase de clôture deux fois (playtest) : la trame
        # ``end`` n'en garde qu'UNE occurrence, sans rien avoir perdu avant.
        doubled = f"{''.join(TOKENS)} {STORY_PAGINATION_SENTENCE} " \
                  f"{STORY_PAGINATION_SENTENCE}"
        async def doubled_tokens():
            yield doubled
        socket = FakeWebSocket()
        run(emit_stream(socket, doubled_tokens()))
        final = socket.frames[-1]["text"]
        self.assertEqual(final.count(STORY_PAGINATION_SENTENCE), 1)
        self.assertTrue(final.endswith(STORY_PAGINATION_SENTENCE))

    def test_un_triple_de_l_invitation_espacé_est_fusionne(self):
        # Forme exacte du playtest Natah : trois occurrences séparées par des
        # sauts de ligne, la dernière suivi d'un blanc.  Une seule survit.
        triple = (f"{''.join(TOKENS)}\n\n\n"
                  f"{STORY_PAGINATION_SENTENCE}\n"
                  f"{STORY_PAGINATION_SENTENCE} \n"
                  f"{STORY_PAGINATION_SENTENCE} \n")
        async def triple_tokens():
            yield triple
        socket = FakeWebSocket()
        run(emit_stream(socket, triple_tokens(), story_more=True))
        self.assertEqual(
            socket.frames[-1]["text"].count(STORY_PAGINATION_SENTENCE), 1)
        self.assertTrue(
            socket.frames[-1]["text"].endswith(STORY_PAGINATION_SENTENCE))
        self.assertTrue(socket.frames[-1]["story_more"])

    def test_une_partie_reduite_a_la_cloture_arrete_la_chaine(self):
        # Partie dégénérée (playtest : l'invitation seule postée comme sa
        # propre partie) : la clôture d'archiviste remplace tout et aucune
        # suite n'est promise — « rien à dire » = stop.
        async def closing_only():
            yield STORY_PAGINATION_SENTENCE
        socket = FakeWebSocket()
        run(emit_stream(socket, closing_only(), story_more=True))
        self.assertEqual(socket.frames[-1]["text"], STORY_COMPLETE_SENTENCE)
        self.assertFalse(socket.frames[-1]["story_more"])

    def test_une_invitation_en_plein_recit_est_conservee(self):
        # La fusion ne touche QUE les répétitions TERMINALES : une occurrence
        # suivie d'une autre narration (structure du narrateur) reste en place.
        invite = STORY_PAGINATION_SENTENCE
        open_text = (f"{''.join(TOKENS)} {invite} Les notes d'Albrecht, "
                     f"cinq chapitres. {invite} {invite}")
        self.assertEqual(collapse_repeated_closing(open_text, invite),
                         f"{''.join(TOKENS)} {invite} Les notes d'Albrecht, "
                         f"cinq chapitres. {invite}")


class CanonicalClosingTests(unittest.TestCase):
    def test_partie_sans_cloture_recoit_l_invitation(self):
        # Playtest épuisement : réponses courtes sans clôture alors que le
        # dossier garde des fragments (story_more=True) — l'invitation doit
        # être imposée, sinon le bot s'arrête sans offrir de suite.
        text = "La Mire évoque la Grande Peste, possible lien avec " \
               "l'Infestation."
        out = canonical_story_closing(text, more=True)
        self.assertTrue(out.endswith(STORY_PAGINATION_SENTENCE))
        self.assertEqual(out.count(STORY_PAGINATION_SENTENCE), 1)

    def test_partie_epuisee_sans_cloture_recoit_le_stop(self):
        out = canonical_story_closing("Albrecht s'enfuit vers Tau.",
                                      more=False)
        self.assertTrue(out.endswith(STORY_COMPLETE_SENTENCE))
        self.assertEqual(out.count(STORY_COMPLETE_SENTENCE), 1)

    def test_une_cloture_contradictoire_est_remplacee(self):
        # Le modèle annonce « plus de fragments » alors que story_more=True :
        # la vérité du serveur (la pagination) gagne, l'invitation reprend.
        text = "Roathe poursuit sa quête. " + STORY_COMPLETE_SENTENCE
        out = canonical_story_closing(text, more=True)
        self.assertNotIn(STORY_COMPLETE_SENTENCE, out)
        self.assertTrue(out.endswith(STORY_PAGINATION_SENTENCE))

    def test_une_cloture_empilee_est_reduite_a_une(self):
        # Clôtures empilées (invitation + stop d'archiviste) : seule reste la
        # clôture conforme au curseur.
        text = ("La Lotus use de la Transference. "
                f"{STORY_PAGINATION_SENTENCE} {STORY_COMPLETE_SENTENCE}")
        out = canonical_story_closing(text, more=False)
        self.assertEqual(out.count(STORY_COMPLETE_SENTENCE), 1)
        self.assertNotIn(STORY_PAGINATION_SENTENCE, out)

    def test_le_stop_degenere_demeure_intact(self):
        self.assertEqual(
            canonical_story_closing(STORY_COMPLETE_SENTENCE, more=True),
            STORY_COMPLETE_SENTENCE)


class _StubRag:
    """``resolve()`` renvoie une fenêtre (contexte, story_more) par appel."""

    def __init__(self, pages: list[tuple[str, bool]]) -> None:
        self.pages = pages
        self.calls = 0

    async def resolve(self, search_text, context=None, subject=None,
                      offset=0, exclude_ids=None):
        ctx, more = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        return ctx, None, more, {1, 2, 3}


class _StubRoleplay:
    """``stream()`` émet une réponse toute faite par appel (pas de LLM)."""

    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.calls = 0

    async def stream(self, session, user_text, rag_context=None, **kwargs):
        out = self.outputs[min(self.calls, len(self.outputs) - 1)]
        self.calls += 1
        yield out


class _StubContainer:
    def __init__(self, rag: _StubRag, roleplay: _StubRoleplay) -> None:
        self.rag = rag
        self.roleplay = roleplay


class EmitStoryTurnTests(unittest.TestCase):
    """La partie story saute les fenêtres muettes au lieu de couper la chaîne.

    Un tour dont le modèle ne narre rien (réponse réduite à la seule clôture)
    ne doit ni mentir sur le dossier ni tuer l'enchaînement : le curseur a
    déjà avancé (mémoire d'exclusion), la fenêtre suivante est servie en
    silence, borné par ``STORY_RETRY_LIMIT``.
    """

    def _frames(self, pages, outputs, payload=None):
        payload = payload or STORY_PAYLOAD
        rag = _StubRag(pages)
        roleplay = _StubRoleplay(outputs)
        socket = FakeWebSocket()
        run(emit_story_turn(
            socket, _StubContainer(rag, roleplay), payload,
            str(payload["text"]), "oracle", RAGContext(),
            Session(session_id="s")))
        return socket, rag, roleplay

    def test_une_partie_narree_est_emise_une_fois(self):
        socket, rag, roleplay = self._frames(
            [("Contexte Albrecht.", True)],
            ["Eleanor ferma ses notes dans Höllvania."])
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"],
                         "Eleanor ferma ses notes dans Höllvania.")
        self.assertTrue(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (1, 1))

    def test_une_fenetre_muette_est_sautee_invisiblement(self):
        # Fenêtre 1 : le modèle n'a rien narré (clôture seule) ; la fenêtre 2
        # raconte.  Rien du premier passage ne sort vers le client, la chaîne
        # continue sur la page suivante.
        socket, rag, roleplay = self._frames(
            [("Fenêtre muette.", True), ("Fenêtre vivante.", True)],
            [STORY_COMPLETE_SENTENCE,
             "Eleanor ferma ses notes dans Höllvania."])
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"],
                         "Eleanor ferma ses notes dans Höllvania.")
        self.assertTrue(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (2, 2))

    def test_une_chaine_morte_s_arrete_sur_le_stop_d_archiviste(self):
        # Toutes les fenêtres retryées sont muettes : la partie sert le stop
        # d'archiviste et ne promet aucune suite — jamais une invitation seule.
        socket, rag, roleplay = self._frames(
            [("m1", True), ("m2", True), ("m3", True)],
            [STORY_COMPLETE_SENTENCE] * 3)
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"], STORY_COMPLETE_SENTENCE)
        self.assertFalse(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls),
                         (STORY_RETRY_LIMIT + 1, STORY_RETRY_LIMIT + 1))

    def test_un_dossier_epuise_ne_essaie_pas_de_rebondir(self):
        # story_more=False (vérité du serveur) : pas de retry, une réponse
        # muette devient simplement le stop d'archiviste.
        socket, rag, roleplay = self._frames(
            [("Dossier drainé.", False)],
            [STORY_COMPLETE_SENTENCE])
        self.assertEqual(socket.frames[-1]["text"], STORY_COMPLETE_SENTENCE)
        self.assertFalse(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (1, 1))

    def test_une_fenetre_vraiment_vide_est_sautee_en_silence(self):
        # Playtest Lettie : la fenêtre 1 ne narre RIEN (même pas la clôture),
        # la fenêtre 2 raconte.  Aucune partie vide ne sort vers le client, la
        # chaîne continue sur la page suivante (2 appels RAG + 2 appels LLM).
        socket, rag, roleplay = self._frames(
            [("Fenêtre muette.", True), ("Fenêtre vivante.", True)],
            ["", "Eleanor ferma ses notes dans Höllvania."])
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"],
                         "Eleanor ferma ses notes dans Höllvania.")
        self.assertTrue(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (2, 2))

    def test_une_chaine_de_fenetres_vides_epuisee_abstention_honnete(self):
        # Toutes les visions retryées ne narrent RIEN mais le dossier garde
        # des fragments : jamais une partie vide qui mentirait sur
        # ``story_more`` — l'abstention désaccordée est servie et la promesse
        # de suite reste HONNÊTE (True).
        socket, rag, roleplay = self._frames(
            [("m1", True), ("m2", True), ("m3", True)],
            ["", "", ""])
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"], RAG_ERROR)
        self.assertTrue(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls),
                         (STORY_RETRY_LIMIT + 1, STORY_RETRY_LIMIT + 1))

    def test_une_fenetre_vide_sur_dossier_draine_est_le_stop(self):
        # story_more=False (vérité du serveur) : une partie vide devient le
        # stop d'archiviste, jamais une partie vide ni une invitation.
        socket, rag, roleplay = self._frames(
            [("Dossier drainé.", False)], [""])
        self.assertEqual([f["type"] for f in socket.frames], ["token", "end"])
        self.assertEqual(socket.frames[-1]["text"], STORY_COMPLETE_SENTENCE)
        self.assertFalse(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (1, 1))

    def test_une_fenetre_narree_sur_un_dossier_epuise_s_arrete_net(self):
        # Fenêtre 2 réellement narrée mais le dossier n'a plus rien derrière :
        # la partie s'émet avec le stop (story_more conforme au serveur).
        socket, rag, roleplay = self._frames(
            [("m1", True), ("m2", False)],
            [STORY_COMPLETE_SENTENCE,
             "Eleanor ferma ses notes dans Höllvania."])
        self.assertEqual(socket.frames[-1]["text"],
                         "Eleanor ferma ses notes dans Höllvania.")
        self.assertFalse(socket.frames[-1]["story_more"])
        self.assertEqual((rag.calls, roleplay.calls), (2, 2))

    def test_un_plan_deterministe_ne_fait_jamais_appeler_le_modele(self):
        # Un tour piégé (injection SQL) est rejeté par les courts-circuits
        # avant le RAG et le LLM.
        payload = dict(STORY_PAYLOAD, text="UPDATE users SET is_admin=1; --")
        socket, rag, roleplay = self._frames(
            [("x", True)], ["jamais servi"], payload=payload)
        self.assertEqual(socket.frames[-1]["text"], JAILBREAK_REJECT)
        self.assertEqual((rag.calls, roleplay.calls), (0, 0))


if __name__ == "__main__":
    unittest.main()
