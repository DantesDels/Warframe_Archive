"""S1 contract: sources carry an explicit kind, a valid location and a status."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.sources import (
    InvalidSourceError,
    SourceKind,
    SourceRegistry,
    SourceStatus,
    new_source,
)


class NewSourceTests(unittest.TestCase):
    def test_id_and_timestamp_are_generated(self):
        source = new_source(SourceKind.API, "https://example.com/api")
        self.assertTrue(source.id)
        self.assertTrue(source.added_at)
        self.assertEqual(source.status, SourceStatus.CANDIDATE)

    def test_explicit_id_is_kept(self):
        source = new_source(SourceKind.WEBSITE, "https://example.com", id="src-1")
        self.assertEqual(source.id, "src-1")

    def test_website_and_api_require_an_http_url(self):
        for kind in (SourceKind.WEBSITE, SourceKind.API):
            for location in ("", "not-a-url", "ftp://example.com", "https://"):
                with self.subTest(kind=kind, location=location):
                    with self.assertRaises(InvalidSourceError):
                        new_source(kind, location)

    def test_document_accepts_a_local_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "book.pdf"
            path.touch()
            source = new_source(SourceKind.DOCUMENT, str(path))
            self.assertEqual(source.location, str(path))

    def test_document_accepts_an_http_url(self):
        source = new_source(SourceKind.DOCUMENT, "https://example.com/book.pdf")
        self.assertEqual(source.kind, SourceKind.DOCUMENT)

    def test_document_rejects_an_unsupported_scheme(self):
        with self.assertRaises(InvalidSourceError):
            new_source(SourceKind.DOCUMENT, "ftp://example.com/book.pdf")

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(InvalidSourceError):
            new_source("newsletter", "https://example.com")


class SourceRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = SourceRegistry(Path(self.tmp.name) / "v1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_and_list(self):
        self.registry.add("warframe", new_source(
            SourceKind.WEBSITE, "https://wiki.example.com", id="s1"))
        self.registry.add("warframe", new_source(
            SourceKind.API, "https://api.example.com", id="s2"))
        self.assertEqual([s.id for s in self.registry.list("warframe")],
                         ["s1", "s2"])

    def test_sources_are_isolated_per_universe(self):
        self.registry.add("a", new_source(
            SourceKind.WEBSITE, "https://a.example.com", id="s1"))
        self.assertEqual(self.registry.list("b"), [])

    def test_set_status(self):
        self.registry.add("warframe", new_source(
            SourceKind.WEBSITE, "https://wiki.example.com", id="s1"))
        self.registry.set_status("warframe", "s1", SourceStatus.APPROVED)
        source = self.registry.get("warframe", "s1")
        assert source is not None
        self.assertIs(source.status, SourceStatus.APPROVED)

    def test_remove(self):
        self.registry.add("warframe", new_source(
            SourceKind.WEBSITE, "https://wiki.example.com", id="s1"))
        self.assertTrue(self.registry.remove("warframe", "s1"))
        self.assertFalse(self.registry.remove("warframe", "s1"))

    def test_duplicate_id_is_rejected(self):
        self.registry.add("warframe", new_source(
            SourceKind.WEBSITE, "https://wiki.example.com", id="s1"))
        with self.assertRaises(ValueError):
            self.registry.add("warframe", new_source(
                SourceKind.API, "https://api.example.com", id="s1"))

    def test_sources_are_persisted_as_json(self):
        self.registry.add("warframe", new_source(
            SourceKind.API, "https://api.example.com",
            id="s1", discovered_by="wikipedia"))
        path = self.registry.path_for("warframe")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload[0]["kind"], "api")
        self.assertEqual(payload[0]["discovered_by"], "wikipedia")

    def test_missing_source_returns_none(self):
        self.assertIsNone(self.registry.get("warframe", "absent"))


if __name__ == "__main__":
    unittest.main()
