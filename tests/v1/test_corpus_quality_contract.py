"""Regression contracts for clean, structured, RAG-ready v1 corpora."""

from __future__ import annotations

import json
import lzma
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from warframe_lore.v1.scraper.adapters.outbound.connectors.mediawiki_api import (
    extract_page,
)
from warframe_lore.v1.scraper.collect.binary_text import decode_lzma, looks_binary
from warframe_lore.v1.scraper.collect.dom_clean import dom_to_markdown, html_language
from warframe_lore.v1.scraper.collect.html_extract import html_to_text
from warframe_lore.v1.scraper.collect.language import detect_language
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext
from warframe_lore.v1.scraper.UI.artifacts import emit_artifacts
from warframe_lore.v1.scraper.UI.runtime.rag_chunks import iter_doc_chunks
from warframe_lore.v1.scraper.UI.views.data.tree import (
    data_roots,
    readable_preview,
)

WIKI_HTML = """
<html lang="en"><head>
<script>RLCONF={"wgBreakFrames":true};_rollbarConfig={token:"x"};</script>
<style>.mw-parser-output { color: red; }</style>
</head><body>
<nav>Navigation menu</nav><header>Site header</header>
<div class="OptanonWrapper">Cookie notice</div>
<div class="mw-parser-output">
  <h2>Lore</h2><p>The ancient machines still sleep beneath the dunes.</p>
  <ul><li>First record</li><li>Second record</li></ul>
</div>
<footer>Site footer</footer>
</body></html>
"""


@dataclass
class FakeResponse:
    content: bytes
    from_cache: bool = False
    url: str = "https://example.invalid"
    encoding: str = "utf-8"
    content_type: str = "application/json"


class FakeClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def get(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
        return FakeResponse(json.dumps(self.payload).encode("utf-8"))


class HtmlCleaningContractTests(unittest.TestCase):
    def test_mediawiki_chrome_and_scripts_are_absent(self) -> None:
        text = html_to_text(WIKI_HTML)
        for token in (
            "RLCONF", "_rollbarConfig", "wgBreakFrames", "color:red",
            "OptanonWrapper", "Cookie notice", "Navigation menu",
            "Site header", "Site footer",
        ):
            self.assertNotIn(token, text)
        self.assertIn("The ancient machines still sleep beneath the dunes.", text)
        self.assertIn("First record", text)

    def test_markdown_keeps_headings_and_sections(self) -> None:
        markdown = dom_to_markdown(WIKI_HTML)
        self.assertIn("## Lore", markdown)
        self.assertIn("- First record", markdown)

    def test_inline_spans_preserve_numbers_without_line_breaks(self) -> None:
        html = "<main><p>With over <span>4</span> Million raised.</p></main>"
        self.assertIn("With over 4 Million raised.", dom_to_markdown(html))

    def test_wikitext_keeps_inline_template_labels_and_drops_files(self) -> None:
        from warframe_lore.v1.scraper.collect.wikitext import wikitext_to_markdown

        raw = (
            "{{Infobox|name=Demo}}\n"
            "Signature weapon of {{W|Gauss}} dealing {{D|Impact}}.\n"
            "[[File:Banner.png|center|700px|Caption]]\n"
            "** Nested bullet item\n"
        )
        md = wikitext_to_markdown(raw)
        self.assertIn("Signature weapon of Gauss dealing Impact.", md)
        self.assertNotIn("Infobox", md)
        self.assertNotIn("700px", md)
        self.assertIn("  - Nested bullet item", md)


class LzmaContractTests(unittest.TestCase):
    def test_alone_and_auto_payloads_decode_to_plain_utf8(self) -> None:
        text = "Lore complet — page entière\nDeuxième ligne."
        for fmt in (lzma.FORMAT_ALONE, lzma.FORMAT_XZ):
            payload = lzma.compress(text.encode("utf-8"), format=fmt)
            decoded = decode_lzma(payload)
            self.assertEqual(decoded, text)
            self.assertFalse(looks_binary(decoded))
            self.assertNotIn("b'", decoded)
            self.assertNotIn("\ufffd", decoded)


class LanguageContractTests(unittest.TestCase):
    def test_url_prefix_and_lang_attribute_are_honored(self) -> None:
        english = "The ancient machines still sleep beneath the dunes."
        self.assertEqual(
            "en", detect_language(
                "https://en.wikipedia.org/wiki/X", english
            )
        )
        self.assertEqual(
            "fr", detect_language(
                "https://fr.wikipedia.org/wiki/X", english
            )
        )
        self.assertEqual("fr", html_language('<html lang="fr-CA"></html>'))
        self.assertEqual(
            "fr", detect_language(
                "https://example.com/en/page", "Les machines anciennes dorment.",
                html_language('<html lang="fr"></html>'),
            )
        )

    def test_english_text_is_not_defaulted_to_french(self) -> None:
        text = "The archives contain ancient records about the great machine."
        self.assertEqual("en", detect_language("https://example.com/wiki/X", text))


class MediaWikiStructureContractTests(unittest.TestCase):
    def test_page_records_include_categories_markdown_and_sections(self) -> None:
        payload = {"query": {"pages": {"12": {
            "pageid": 12,
            "title": "Exemple",
            "fullurl": "https://wiki.example.org/wiki/Exemple",
            "extract": "Ancien texte",
            "categories": [{"title": "Category:Lore"}],
            "revisions": [{
                "revid": 99,
                "timestamp": "2026-01-02T03:04:05Z",
                "slots": {"main": {"*": (
                    "{{Infobox|name=Exemple}}\n"
                    "== Histoire ==\n"
                    "Texte complet de la page.\n"
                    "== Détails ==\n"
                    "[[Lien|Autre page]]\n"
                    "[[Category:Fanon]]"
                )}},
            }],
        }}}}
        ctx = ConnectorContext(client=FakeClient(payload), limits={})
        page = extract_page(ctx, "https://wiki.example.org/api.php", "Exemple")[0]
        metadata = page.metadata
        self.assertEqual("text/markdown", page.content_type)
        self.assertEqual("## Histoire", metadata["content_markdown"].splitlines()[0])
        self.assertNotIn("Infobox", metadata["content_markdown"])
        self.assertEqual("Lore, Fanon", metadata["category"])
        self.assertEqual("speculation", metadata["canon_status"])
        self.assertEqual(2, len(metadata["sections"]))
        self.assertEqual(
            ("Exemple", "Histoire", "Texte complet de la page."),
            tuple(metadata["sections"][0].values()),
        )


class StructuredExportContractTests(unittest.TestCase):
    def test_bucket_json_and_full_markdown_are_generated(self) -> None:
        long_text = "Texte long et complet. " * 400
        docs = [{
            "id": "doc-1", "title": "Exemple", "url": "https://example.org/x",
            "docType": "wiki", "language": "fr", "category": "Lore",
            "canon_status": "canon", "last_updated": "2026-01-02",
            "page_title": "Exemple", "page_url": "https://example.org/x",
            "source_api": "https://wiki.example.org/api.php",
            "content": long_text, "content_markdown": long_text,
            "sections": [{"titre_page": "Exemple", "section": "Histoire",
                          "contenu": long_text}],
        }, {
            "id": "doc-2", "title": "Rumeur", "url": "https://example.org/y",
            "docType": "wiki", "language": "en", "category": "Rumeurs",
            "canon_status": "speculation", "content": "Short rumor text.",
            "content_markdown": "Short rumor text.", "sections": [],
        }]
        universe = {"id": "u1", "name": "Warframe"}
        with tempfile.TemporaryDirectory() as temp:
            out_dir = Path(temp)
            manifest = emit_artifacts(
                out_dir, universe, docs,
                ["json", "jsonl", "csv", "markdown", "sql", "nosql"],
            )
            bucket = json.loads(
                (out_dir / "Lore_FR.json").read_text(encoding="utf-8")
            )
            self.assertEqual("Lore", bucket["metadata"]["bucket_title"])
            self.assertEqual(1, bucket["metadata"]["total_pages"])
            self.assertIn("generated_at", bucket["metadata"])
            self.assertIn("source_api", bucket["metadata"])
            self.assertEqual(long_text, bucket["pages"][0]["content_markdown"])
            self.assertEqual(1, len(bucket["pages"][0]["sections"]))
            self.assertTrue((out_dir / "Rumeurs_EN.json").exists())
            complete = (out_dir / "Warframe_Complete.md").read_text(encoding="utf-8")
            self.assertIn("## Bucket: Lore", complete)
            self.assertIn("### Exemple", complete)
            self.assertIn(long_text, complete)
            self.assertNotIn(long_text[:320] + "\n\n[...", complete)
            canon = (out_dir / "Warframe_Canon.md").read_text(encoding="utf-8")
            self.assertIn("### Exemple", canon)
            self.assertNotIn("### Rumeur", canon)
            for name in (
                "documents.json", "documents.jsonl", "documents.csv",
                "documents.sql", "documents.nosql.json",
            ):
                self.assertTrue((out_dir / name).exists(), name)
            self.assertNotIn("b'", (out_dir / "documents.csv").read_text(
                encoding="utf-8"
            ))
            self.assertEqual(2, manifest["document_count"])

    def test_large_bucket_count_consolidates_singletons_into_general(self) -> None:
        docs = [
            {
                "id": f"d-{i}", "title": f"Page {i}",
                "url": f"https://wiki.example.org/wiki/P{i}",
                "docType": "wiki", "language": "en",
                "category": "Major" if i < 4 else f"Singleton{i}",
                "content": f"Content for page {i}.",
            }
            for i in range(18)
        ]
        with tempfile.TemporaryDirectory() as temp:
            out_dir = Path(temp)
            emit_artifacts(out_dir, {"id": "u1", "name": "Demo"}, docs, ["json"])
            self.assertTrue((out_dir / "Major_EN.json").exists())
            self.assertTrue((out_dir / "General_EN.json").exists())
            self.assertFalse((out_dir / "Singleton10_EN.json").exists())
            general = json.loads(
                (out_dir / "General_EN.json").read_text(encoding="utf-8")
            )
            self.assertEqual(general["metadata"]["total_pages"], 14)

    def test_manifest_extracts_relative_filenames_with_digests(self) -> None:
        from warframe_lore.v1.scraper.collect.manifest import extract_manifest_urls

        index_text = "ExportWarframes_en.json!00_abc123\nExportWeapons_en.json!00_def\n"
        urls = extract_manifest_urls(
            index_text,
            "https://cdn.example.com/export/index_en.txt.lzma",
            manifest_base="https://cdn.example.com/export/Manifest/",
        )
        self.assertEqual(
            urls,
            [
                "https://cdn.example.com/export/Manifest/ExportWarframes_en.json!00_abc123",
                "https://cdn.example.com/export/Manifest/ExportWeapons_en.json!00_def",
            ],
        )


class DataTabContractTests(unittest.TestCase):
    def test_local_corpus_roots_and_dialogue_previews_are_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            workspace_path = base / "workspace.json"
            out = base / "out"
            out.mkdir()
            (out / "record.dialogue").write_text("Ligne de dialogue.", encoding="utf-8")
            (out / "data.json").write_text('{"a": 1}', encoding="utf-8")
            (base / "exports" / "u1").mkdir(parents=True)

            class FakeWorkspace:
                path = workspace_path

                def sources_for(self, universe_id: str) -> list[dict[str, Any]]:
                    return [{
                        "kind": "local_directory", "location": str(out),
                        "universeId": universe_id,
                    }]

            roots = data_roots(FakeWorkspace(), "u1")
            self.assertIn(out, roots)
            self.assertIn(base / "exports" / "u1", roots)
            dialogue = readable_preview(out / "record.dialogue")
            self.assertIn("Ligne de dialogue.", dialogue)
            self.assertIn('"a": 1', readable_preview(out / "data.json"))


class RagChunkingContractTests(unittest.TestCase):
    def test_chunks_follow_structured_sections(self) -> None:
        doc = {
            "id": "d1", "content": "texte brut",
            "sections": [
                {"titre_page": "Page", "section": "Histoire", "contenu": "A" * 50},
                {"titre_page": "Page", "section": "Details", "contenu": "B" * 50},
            ],
        }
        chunks = list(iter_doc_chunks(doc))
        self.assertEqual(["Histoire", "Details"], [part[1] for part in chunks])
        self.assertEqual("A" * 50, chunks[0][0])
        self.assertEqual("B" * 50, chunks[1][0])

    def test_chunks_fall_back_to_markdown_when_no_sections(self) -> None:
        doc = {"id": "d2", "content": "brut", "content_markdown": "Markdown entier."}
        chunks = list(iter_doc_chunks(doc))
        self.assertEqual([("Markdown entier.", "")], chunks)


if __name__ == "__main__":
    unittest.main()
