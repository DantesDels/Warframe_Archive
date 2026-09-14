"""Le bot doit démarrer : chaîne d'import, CLI, et découplage de la pile RAG/DB.

Cas réel : une casse d'import dans ``engram.rag`` — paquet frère que le bot
n'exécute pas — a empêché ``cephalon bot run`` de démarrer.  Ces tests
verrouillent le chemin de lancement : TOUS les modules du bot s'importent, la CLI
répond, la sortie sans token est propre, et la pile base de données n'est jamais
chargée par le processus du bot (façade RAG paresseuse).
"""

from __future__ import annotations

import ast
import importlib
import os
import pkgutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import warframe_lore.discord

REPO_ROOT = Path(__file__).resolve().parents[1]

# Ce que le processus du bot ne doit JAMAIS charger (ni lui, ni ses dépendances).
FORBIDDEN = ("sqlalchemy", "asyncpg", "fastapi", "starlette", "uvicorn",
             "warframe_lore.db", "warframe_lore.api", "warframe_lore.cleaner")

PROBE = """
import sys
import warframe_lore.discord.main  # noqa: F401
forbidden = {forbidden!r}
loaded = sorted(m for m in sys.modules
                if any(m == f or m.startswith(f + ".") for f in forbidden))
print("LOADED", loaded)
print("TOTAL", len([m for m in sys.modules if m.startswith("warframe_lore")]))
"""


class ImportChainTests(unittest.TestCase):
    """Chaque module du bot est importable : la casse d'import est bloquante."""

    def test_tous_les_modules_du_bot_s_importent(self):
        failed = []
        for info in pkgutil.walk_packages(warframe_lore.discord.__path__,
                                          "warframe_lore.discord."):
            try:
                importlib.import_module(info.name)
            except Exception as exc:  # noqa: BLE001 — on liste, on n'interrompt pas
                failed.append(f"{info.name}: {exc}")
        self.assertEqual(failed, [])

    def test_le_point_d_entree_console_s_importe(self):
        self.assertTrue(callable(importlib.import_module(
            "warframe_lore.discord.main").launch_bot))


class DecouplingTests(unittest.TestCase):
    """Le bot n'embarque ni SQLAlchemy, ni la base, ni l'API HTTP."""

    def probe(self) -> tuple[list[str], int]:
        script = PROBE.format(forbidden=FORBIDDEN)
        done = subprocess.run([sys.executable, "-c", script],
                              capture_output=True, text=True, timeout=180,
                              check=True, cwd=str(REPO_ROOT))
        values = {}
        for line in done.stdout.splitlines():
            key, _, raw = line.partition(" ")
            values[key] = raw
        return ast.literal_eval(values["LOADED"]), int(values["TOTAL"])

    def test_aucune_pile_base_de_donnee_chargée(self):
        loaded, _ = self.probe()
        self.assertEqual(loaded, [])

    def test_cloture_d_import_bornée(self):
        # Garde-fou anti-ré-couplage : la façade RAG paresseuse doit rester
        # paresseuse (la pile DB/API ferait exploser ce compteur).
        _, total = self.probe()
        self.assertLess(total, 120, f"{total} modules warframe_lore chargés")


class LaunchTests(unittest.TestCase):
    def test_sans_token_sortie_propre_sans_effet_de_bord(self):
        launch_bot = importlib.import_module(
            "warframe_lore.discord.main").launch_bot
        with mock.patch.dict(os.environ, {"DISCORD_TOKEN": ""}):
            self.assertEqual(launch_bot(None), 2)

    def test_cephalon_bot_run_expose_ses_options(self):
        main = importlib.import_module("warframe_lore.cli").main
        with self.assertRaises(SystemExit) as caught:
            main(["bot", "run", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
