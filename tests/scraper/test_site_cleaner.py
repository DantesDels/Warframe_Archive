"""HtmlCleaner tests (HTML -> Markdown for the official site pages)."""

from __future__ import annotations

import unittest

from warframe_lore.cleaner import CleanOutput, HtmlCleaner


class HtmlCleanerTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = HtmlCleaner()

    def test_strips_chrome_and_converts_content(self):
        html = (
            "<nav><a href='/fr/shop'>Boutique</a></nav>"
            "<h1>Bienvenue</h1>"
            "<p>Texte <strong>gras</strong> et <em>italique</em>.</p>"
            "<ul><li>Un</li><li>Deux</li></ul>"
            "<footer><p>©2026 Digital Extremes</p></footer>"
            "<script>var x = 1;</script>"
        )
        out = self.cleaner.clean(html)
        self.assertIsInstance(out, CleanOutput)
        self.assertEqual(out.non_canon_detected_in_body, False)
        md = out.markdown
        self.assertTrue(md.startswith("# Bienvenue"))
        self.assertIn("**gras**", md)
        self.assertIn("*italique*", md)
        self.assertIn("- Un", md)
        self.assertIn("- Deux", md)
        self.assertNotIn("Boutique", md)
        self.assertNotIn("©2026", md)

    def test_tables_become_plain_separated_text(self):
        html = "<h2>Patch</h2><p>a</p><table><tr><td>x</td><td>y</td></tr></table>"
        out = self.cleaner.clean(html)
        self.assertTrue(out.markdown.startswith("## Patch"))
        self.assertIn("x", out.markdown)
        self.assertIn("y", out.markdown)

    def test_empty_page_yields_empty_markdown(self):
        out = self.cleaner.clean("<script>drop()</script><nav>menu</nav>")
        self.assertEqual(out.markdown, "")

    def test_unclosed_video_must_not_swallow_the_page(self):
        html = (
            "<title>Warframe: Saryn</title>"
            "<h1>Saryn</h1>"
            "<p>La toxicité est la force de Saryn.</p>"
            "<video src='/x.mp4'>"
            "<div class='abilities'>"
            "<h2>Pouvoirs</h2><p>Miasme</p>"
            "</div>"
            "<footer><p>bas de page</p></footer>"
        )
        out = self.cleaner.clean(html)
        md = out.markdown
        self.assertIn("toxicité", md)
        self.assertIn("Pouvoirs", md)
        self.assertNotIn("bas de page", md)


if __name__ == "__main__":
    unittest.main()
