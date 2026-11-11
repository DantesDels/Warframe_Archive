"""Troncature stricte (hard split) sur le marqueur de fin de génération.

Le paramètre ``stop`` de l'API LLM peut échouer silencieusement : le modèle
continue de générer après ``*[Indexation terminée]*``. Côté client Discord,
le buffer est donc TRONQUÉ à la détection du marqueur, le WebSocket est
fermé (le flux résiduel est abandonné) et l'édition finale est envoyée.
"""

from __future__ import annotations

import asyncio
import unittest

from warframe_lore.discord.services.transport import (
    STOP_MARKER,
    MessageStreamer,
    RoleplayGateway,
)
from warframe_lore.protocols.roleplay import MessageFrame


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeMessage:
    def __init__(self):
        self.content = "*Oracle réfléchit…*"

    async def edit(self, content=None):
        self.content = content


class StreamerHardSplitTests(unittest.TestCase):
    def test_buffer_tronque_au_marqueur_et_edition_finale(self):
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        _run(streamer.add("texte avant "))
        self.assertEqual(msg.content, "texte avant ")  # 1er jeton : flush
        stopped = _run(streamer.add(f"{STOP_MARKER} déchets résiduels"))
        self.assertTrue(stopped)  # hard split : True = couper le flux
        self.assertEqual(
            msg.content,
            f"texte avant \n\n{STOP_MARKER}")
        self.assertEqual(streamer.text, msg.content)

    def test_marqueur_debut_puis_fin_reelle_au_milieu(self):
        """Marqueur décoratif en tête puis vrai marqueur de fin: le second
        déclenche le hard split (contenu présent avant lui)."""
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        _run(streamer.add(f"*{STOP_MARKER}* contenu "))
        stopped = _run(streamer.add(f"{STOP_MARKER} déchets"))
        self.assertTrue(stopped)
        self.assertTrue(
            msg.content.startswith("* contenu \n\n" + STOP_MARKER))

    def test_marqueur_au_debut_reponse_n_est_pas_un_hard_split(self):
        """Une réponse qui COMMENCE par le marqueur (déco RP) doit l'ôter
        du buffer SANS tronquer la suite ni fermer le flux."""
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        stopped = _run(streamer.add(f"*{STOP_MARKER}* Voici la vraie réponse"))
        self.assertFalse(stopped)  # pas de fermeture : pas une fin
        self.assertNotIn(STOP_MARKER, streamer.text)
        self.assertIn("Voici la vraie réponse", streamer.text)
        # et un vrai marqueur PLUS TARD déclenche toujours le split
        stopped = _run(streamer.add(f" final.{STOP_MARKER}reliquat"))
        self.assertTrue(stopped)
        self.assertEqual(
            msg.content,
            f"* Voici la vraie réponse final.\n\n{STOP_MARKER}")

    def test_sans_marqueur_retourne_false_et_garde_le_flux(self):
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        ok = _run(streamer.add("flot normal"))
        self.assertFalse(ok)
        self.assertEqual(msg.content, "flot normal")

    def test_marqueur_etale_sur_plusieurs_jetons_detecte(self):
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        _run(streamer.add("réponse "))
        stopped = _run(streamer.add("[Indexation ter"))
        self.assertFalse(stopped)  # pas encore complet
        stopped = _run(streamer.add("minée]"))
        self.assertTrue(stopped)
        self.assertEqual(msg.content, f"réponse \n\n{STOP_MARKER}")

    def test_finish_purge_l_artefact_trailing_avant_l_edition_finale(self):
        """Fix Q7 (émission Discord) : le message est construit depuis les
        JETONS (frame ``end`` non consommée par le bot) → la purge de fin
        s'applique au buffer juste avant l'édition finale."""
        msg = _FakeMessage()
        streamer = MessageStreamer(msg, update_every=1000, min_interval=1000.0)
        _run(streamer.add("réponse * "))
        self.assertEqual(msg.content, "réponse * ")  # édition intermédiaire
        _run(streamer.finish())
        self.assertEqual(msg.content, "réponse")     # édition finale purgée


class _FakeConn:
    """Mime la connexion WebSocket : capture les frames envoyées."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


class _FakeGateway(RoleplayGateway):
    """Gateway pilotée par une file pré-remplie (aucun réseau)."""

    def __init__(self, frames, conn):
        super().__init__("ws://fake")
        self._conn = conn
        self._closed = False
        for frame in frames:
            self._queue.put_nowait(frame)

    @property
    def active(self):
        return not self._closed

    async def open(self):
        pass


class GatewayHardSplitTests(unittest.TestCase):
    def test_hard_split_ferme_le_websocket_et_ne_attend_pas_end(self):
        conn = _FakeConn()
        frames = [
            {"type": "token", "token": f"*{STOP_MARKER}* déchets"},
            # pas de frame "end" : le flux doit quand même s'arrêter.
        ]
        gw = _FakeGateway(frames, conn)
        received = []

        async def on_token(token):
            received.append(token)
            return STOP_MARKER in token

        _run(gw.send(MessageFrame(text="question", rag=True),
                     on_token=on_token))
        self.assertTrue(conn.closed)          # WS fermé (flux résiduel coupé)
        self.assertTrue(gw._closed)
        self.assertIn("déchets", received[0])  # le jeton a bien été vu

    def test_flux_normal_se_termine_sur_end(self):
        conn = _FakeConn()
        frames = [
            {"type": "token", "token": "bonjour"},
            {"type": "end", "text": "bonjour"},
        ]
        gw = _FakeGateway(frames, conn)
        received = []

        async def on_token(token):
            received.append(token)
            return False

        _run(gw.send(MessageFrame(text="question"), on_token=on_token))
        self.assertFalse(conn.closed)          # pas de marqueur : WS intact
        self.assertEqual(received, ["bonjour"])


if __name__ == "__main__":
    unittest.main()
