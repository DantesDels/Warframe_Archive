"""Regression contracts for DOM-aware HTML text extraction."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.collect.html_extract import html_to_text


class HtmlExtractionContractTests(unittest.TestCase):
    def test_wikipedia_script_payload_is_absent_from_excerpt_and_content(self) -> None:
        html = (
            "<html><head><title>Exemple</title></head><body>"
            "<script>(function(){"
            "var className='mw-parser-output';"
            "window.RLQ=window.RLQ||[];"
            "RLQ.push(function(){mw.loader.load('site');});"
            "})();</script>"
            "<p>Le texte lore visible doit rester seul.</p>"
            "</body></html>"
        )
        content = html_to_text(html)
        excerpt = content[:320]
        for token in ("(function()", "var className", "window.RLQ", "mw.loader"):
            self.assertNotIn(token, content)
            self.assertNotIn(token, excerpt)
        self.assertIn("Le texte lore visible doit rester seul.", content)
        self.assertIn("Le texte lore visible doit rester seul.", excerpt)

    def test_non_content_elements_and_inline_handlers_are_dropped(self) -> None:
        html = (
            "<main><style>.x{color:red}</style>"
            "<noscript>Activer JavaScript</noscript>"
            "<template><p>Modèle caché</p></template>"
            "<svg><text>Image vectorielle</text></svg>"
            "<div onclick=\"alert('x')\">Contenu autorisé</div>"
            "<a href=\"javascript:alert(1)\">Lien sûr</a></main>"
        )
        content = html_to_text(html)
        self.assertIn("Contenu autorisé", content)
        self.assertIn("Lien sûr", content)
        for token in (
            "color:red",
            "Activer JavaScript",
            "Modèle caché",
            "Image vectorielle",
            "alert(",
            "javascript:",
        ):
            self.assertNotIn(token, content)


if __name__ == "__main__":
    unittest.main()
