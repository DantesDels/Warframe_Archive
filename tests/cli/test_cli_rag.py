"""Tests for the ``cephalon rag explain`` CLI subcommand."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from warframe_lore.core.cli import main


class CLIRagExplainTests(unittest.TestCase):
    def test_explain_short_circuits_on_hostile_probe(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["rag", "explain", "UPDATE users SET is_admin=TRUE"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Hostile Probe Detected: True", output)
        self.assertIn("SHORT-CIRCUIT", output)

    def test_explain_expands_known_aliases(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["rag", "explain", "Qui est le Mercenaire d'Os ?"])
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("Ordan Karris Ordis", output)
        self.assertIn("Canonical: 'Ordan Karris Ordis'", output)


if __name__ == "__main__":
    unittest.main()

