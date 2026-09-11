"""Semantic chunking: sections, context prefix and structured ingestion.

Covers the parser refactoring -- every chunk of a cleaned page is built
from its semantic section and vectorized WITH its context
(``Page: X | Section: Y - ...``), and the ingestion pipeline accepts the
structured ``{"titre_page", "section", "contenu"}`` list."""

import unittest

from warframe_lore.db import ChunkManager, sections_from_markdown
from warframe_lore.db.chunks.split import DEFAULT_CHUNK_MAX_CHARACTERS


class SemanticSectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.page = "# Ordis\n\n## Identité passée\n\nAvant de devenir " \
            "un Cephalon, Ordis était un mercenaire nommé Ordan Karris.\n\n" \
            "## Rôle actuel\n\nIl est l'opérateur du vaisseau Orbiteur."

    def test_sections_are_split_per_heading(self):
        sections = sections_from_markdown(self.page, page_title="Ordis")
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["titre_page"], "Ordis")
        self.assertEqual(sections[0]["section"], "Identité passée")
        self.assertIn("Ordan Karris", sections[0]["contenu"])
        self.assertEqual(sections[1]["section"], "Rôle actuel")
        self.assertNotIn("## Identité passée", sections[0]["contenu"])

    def test_contenu_has_no_context_prefix(self):
        sections = sections_from_markdown(self.page, page_title="Ordis")
        for section in sections:
            self.assertNotIn("Page: ", section["contenu"])
            self.assertNotIn("Section: ", section["contenu"])

    def test_nested_heading_chain(self):
        nested = "# WF\n\n## Ordis\n\n### Ordan Karris\n\nUn mercenaire."
        sections = sections_from_markdown(nested, page_title="Ordis")
        self.assertEqual(sections[0]["section"], "Ordis > Ordan Karris")

    def test_page_title_unknown_keeps_legacy_split(self):
        manager = ChunkManager()
        chunks = manager.split(self.page, page_title="")
        self.assertNotIn("Page: ", chunks[0].content_markdown)
        self.assertNotEqual(chunks[0].metadata.get("page_title"), "Ordis")


class ContextPrefixTests(unittest.TestCase):
    def test_each_chunk_carries_page_and_section_context(self):
        manager = ChunkManager(
            chunk_max_characters=80, chunk_overlap_characters=10)
        chunks = manager.split(
            "# Ordis\n\n## Identité passée\n\nAvant de devenir un Cephalon, "
            "Ordis était un mercenaire nommé Ordan Karris. Il a perdu la "
            "mémoire lors de sa transformation.",
            page_title="Ordis",
        )
        self.assertGreater(len(chunks), 1, "long section must be re-split")
        for chunk in chunks:
            self.assertTrue(
                chunk.content_markdown.startswith(
                    "Page: Ordis | Section: Identité passée - "),
                chunk.content_markdown[:60],
            )
            self.assertEqual(chunk.metadata["page_title"], "Ordis")
            self.assertEqual(chunk.metadata["section"], "Identité passée")

    def test_page_prefix_without_section(self):
        manager = ChunkManager()
        chunks = manager.split("Une préface brute.", page_title="Ordis")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(
            chunks[0].content_markdown, "Page: Ordis - Une préface brute.")
        self.assertNotIn("| Section:", chunks[0].content_markdown)


class StructuredIngestionTests(unittest.TestCase):
    def test_from_sections_uses_french_keys(self):
        manager = ChunkManager()
        chunks = manager.from_sections([
            {"titre_page": "Ordis", "section": "Identité passée",
             "contenu": "Autrefois, Ordis était Ordan Karris."},
            {"titre_page": "Ordis", "section": "Rôle actuel",
             "contenu": "Il gère l'Orbiteur."},
        ])
        self.assertEqual(len(chunks), 2)
        self.assertIn("Page: Ordis | Section: Identité passée - ",
                      chunks[0].content_markdown)
        self.assertIn("Page: Ordis | Section: Rôle actuel - ",
                      chunks[1].content_markdown)
        self.assertIn("Ordan Karris", chunks[0].content_markdown)

    def test_from_sections_skips_empty_bodies(self):
        manager = ChunkManager()
        chunks = manager.from_sections([
            {"titre_page": "Ordis", "section": "Vide", "contenu": "   "},
            {"titre_page": "Ordis", "section": "Rempli",
             "contenu": "Du contenu."},
        ])
        self.assertEqual(len(chunks), 1)

    def test_round_trip_matches_split_output(self):
        manager = ChunkManager()
        markdown = "# Ordis\n\n## Identité passée\n\n" \
            "Avant de devenir un Cephalon, Ordis était un mercenaire nommé " \
            "Ordan Karris."
        expected = manager.split(markdown, page_title="Ordis")
        rebuilt = manager.from_sections(
            sections_from_markdown(markdown, page_title="Ordis"))
        self.assertEqual(
            [c.content_markdown for c in expected],
            [c.content_markdown for c in rebuilt],
        )

    def test_sizes_are_respected_without_dialogue_mode(self):
        sections = sections_from_markdown(
            "## Longue section\n\n" + "mot " * 400, page_title="Test")
        self.assertTrue(sections)
        for section in sections:
            self.assertLessEqual(
                len(section["contenu"]), DEFAULT_CHUNK_MAX_CHARACTERS)


if __name__ == "__main__":
    unittest.main()