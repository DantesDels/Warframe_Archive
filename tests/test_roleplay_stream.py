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
    collapse_repeated_closing,
    emit_stream,
)
from warframe_lore.engram.roleplay.prompt import (
    STORY_COMPLETE_SENTENCE,
    STORY_PAGINATION_SENTENCE,
)

TOKENS = ("Ballas fut le ", "Conseiller ", "des Orokin.")


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


if __name__ == "__main__":
    unittest.main()
