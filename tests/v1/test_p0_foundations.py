"""P0 foundation contracts: connectors, pipeline, security, versioning, manifest."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.adapters.outbound.connectors.registry import (
    default_registry,
)
from warframe_lore.v1.scraper.adapters.outbound.persistence.event_log import (
    JsonlEventLogAdapter,
)
from warframe_lore.v1.scraper.adapters.outbound.security.fetch_policy import (
    check_payload,
    check_url,
)
from warframe_lore.v1.scraper.pipeline.base import PipelineContext, PipelineItem
from warframe_lore.v1.scraper.pipeline.default import default_pipeline
from warframe_lore.v1.scraper.ports.outbound.sources import (
    CollectedPage,
    ConnectorContext,
)
from warframe_lore.v1.scraper.storage import read_json
from warframe_lore.v1.scraper.UI.artifacts import emit_artifacts
from warframe_lore.v1.scraper.UI.models import UniverseWorkspace
from warframe_lore.v1.scraper.use_cases.apply_result import apply_result


class JsonStorageTests(unittest.TestCase):
    def test_corrupt_file_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "workspace.json"
            path.write_text("{invalid json", encoding="utf-8")
            self.assertEqual(read_json(path, {"fallback": True}), {"fallback": True})

    def test_missing_file_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_json(Path(tmp) / "absent.json", []), [])


class ConnectorRegistryTests(unittest.TestCase):
    def test_registry_resolves_document_connector(self):
        reg = default_registry()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("hello")
            name = f.name
        try:
            ctx = ConnectorContext(client=None, limits={})
            connector = reg.resolve({"location": name, "kind": "document"}, ctx)
            self.assertEqual(connector.name, "document")
        finally:
            Path(name).unlink(missing_ok=True)


class SecurityGateTests(unittest.TestCase):
    def test_blocks_private_url(self):
        res = check_url("http://127.0.0.1/secret")
        self.assertFalse(res.allowed)
        self.assertEqual(res.code, "blocked_private_ip")

    def test_blocks_executable_payload(self):
        res = check_payload("https://example.org/a.bin", b"MZbad",
                            "application/octet-stream")
        self.assertFalse(res.allowed)

    def test_blocks_oversized_payload(self):
        from warframe_lore.v1.scraper.adapters.outbound.security.fetch_policy import (
            FetchPolicy,
        )
        res = check_payload("https://example.org/a.txt", b"x" * 20,
                            "text/plain", FetchPolicy(max_bytes=10))
        self.assertFalse(res.allowed)
        self.assertEqual(res.code, "blocked_max_bytes")


class PipelineTests(unittest.TestCase):
    def test_pipeline_dedupes_and_normalizes(self):
        pages = [
            CollectedPage("A", "https://a.test/x", "Hello  \n\n world"),
            CollectedPage("A2", "https://a.test/x/", "duplicate"),
            CollectedPage("B", "https://a.test/y", "  \n"),
        ]
        items = [PipelineItem(page=p) for p in pages]
        ctx = PipelineContext(source={}, universe_id="u", settings={})
        out = default_pipeline().run(items, ctx)
        urls = [i.page.url for i in out]
        self.assertEqual(urls, ["https://a.test/x"])
        self.assertEqual(out[0].page.content, "Hello\nworld")


class VersioningTests(unittest.TestCase):
    def test_apply_result_upserts_and_versions(self):
        ws = UniverseWorkspace(data={
            "universes": [{"id": "u1", "name": "U"}], "sources": [],
            "documents": [], "document_versions": [], "runs": [],
            "candidates": [], "capabilities": {},
        })
        doc1 = {
            "id": "d1", "universeId": "u1", "url": "https://a",
            "contentHash": "h1", "title": "A",
        }
        run1 = {"id": "run1", "status": "done", "universeIds": ["u1"]}
        apply_result(ws, {"runs": [{
            "universeId": "u1", "docs": [doc1], "run": run1
        }]})
        self.assertEqual(len(ws.data["documents"]), 1)
        self.assertEqual(ws.data["documents"][0]["version"], 1)

        doc2 = {"id": "d1b", "universeId": "u1", "url": "https://a",
                "contentHash": "h2", "title": "A2"}
        run2 = {"id": "run2", "status": "done", "universeIds": ["u1"]}
        apply_result(ws, {"runs": [{
            "universeId": "u1", "docs": [doc2], "run": run2}]})
        self.assertEqual(len(ws.data["documents"]), 1)
        self.assertEqual(ws.data["documents"][0]["contentHash"], "h2")
        self.assertEqual(ws.data["documents"][0]["version"], 2)
        self.assertEqual(len(ws.data["document_versions"]), 1)
        self.assertEqual(ws.data["document_versions"][0]["previousHash"], "h1")


class ManifestAndEventsTests(unittest.TestCase):
    def test_manifest_has_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            docs = [{"id": "d1", "title": "T", "url": "u", "excerpt": "e"}]
            manifest = emit_artifacts(out, {"id": "u1", "name": "U"}, docs, ["json"])
            self.assertTrue((out / "manifest.json").is_file())
            self.assertEqual(manifest["document_count"], 1)
            self.assertTrue(manifest["files"])
            self.assertEqual(len(manifest["files"][0]["sha256"]), 64)

    def test_event_log_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = JsonlEventLogAdapter(Path(tmp) / "events.jsonl")
            log.emit("run_started", universe="u1")
            log.emit("run_finished", ok=True)
            path = Path(tmp) / "events.jsonl"
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["type"], "run_started")
