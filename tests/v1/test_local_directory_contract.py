"""Generic recursive local-directory ingestion contracts."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from warframe_lore.v1.scraper.adapters.outbound.connectors.local_directory import (
    LOGGER,
    LocalDirectoryConnector,
)
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext
from warframe_lore.v1.scraper.use_cases.collect_source import collect_source


class _Client:
    def get(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("local sources must not use the HTTP client")


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class LocalDirectoryConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _write(self.root / "out" / "alpha.json", {
            "title": "Alpha", "language": "fr", "body": "Texte lore en français."
        })
        _write(self.root / "corpus" / "data" / "player.json", {
            "lang": "en", "name": "Tenno"
        })
        (self.root / "corpus" / "dicts").mkdir(parents=True)
        (self.root / "corpus" / "dicts" / "terms.jsonl").write_text(
            '{"term":"one"}\n{"term":"two"}\n', encoding="utf-8"
        )
        (self.root / "corpus" / "notes.md").write_text(
            "# Notes\n\nTexte.", encoding="utf-8"
        )
        (self.root / "_precheck.py").write_text(
            "print('skip me')\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _source(self) -> dict[str, str]:
        return {
            "id": "src-local",
            "kind": "local_directory",
            "location": str(self.root),
        }

    def _collect(self) -> tuple[list[dict[str, object]], dict[str, object]]:
        source = self._source()
        with self.assertLogs(LOGGER, level="INFO") as logs:
            pages = LocalDirectoryConnector().collect(
                source, ConnectorContext(client=_Client(), limits={})
            )
        self.assertTrue(any("_precheck.py" in line for line in logs.output))
        titles = [page.title for page in pages]
        self.assertEqual(
            titles,
            [
                "corpus/data/player.json",
                "corpus/dicts/terms.jsonl",
                "corpus/notes.md",
                "out/alpha.json",
            ],
        )
        state: dict[str, object] = {}
        limits = {"incremental": True, "expand_manifests": False}
        docs, errors, updates = collect_source(
            source, "universe", _Client(), limits, state
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(updates), len(pages))
        state.update({item["url"]: {"hash": item["hash"]} for item in updates})
        return docs, state

    def test_files_become_distinct_documents_with_metadata(self) -> None:
        docs, _state = self._collect()
        by_url = {str(doc["url"]): doc for doc in docs}
        alpha = by_url[str(self.root / "out" / "alpha.json")]
        self.assertEqual(alpha["title"], "out/alpha.json")
        self.assertEqual(alpha["docType"], "json")
        self.assertEqual(alpha["language"], "fr")
        digest = hashlib.sha256(
            (self.root / "out" / "alpha.json").read_bytes()
        ).hexdigest()
        self.assertEqual(alpha["contentHash"], digest)
        self.assertIn("Alpha", str(alpha["excerpt"]))
        self.assertIn("Alpha", str(alpha["content"]))
        player = by_url[str(self.root / "corpus" / "data" / "player.json")]
        self.assertEqual(player["language"], "en")
        notes = by_url[str(self.root / "corpus" / "notes.md")]
        self.assertEqual(notes["docType"], "md")

    def test_incremental_rerun_only_updates_modified_files(self) -> None:
        _docs, state = self._collect()
        source = self._source()
        limits = {"incremental": True, "expand_manifests": False}
        unchanged, _, _ = collect_source(
            source, "universe", _Client(), limits, state
        )
        self.assertEqual(unchanged, [])

        target = self.root / "out" / "alpha.json"
        _write(target, {"title": "Alpha", "language": "fr", "body": "Nouveau texte."})
        changed, _, updates = collect_source(
            source, "universe", _Client(), limits, state
        )
        self.assertEqual([str(doc["url"]) for doc in changed], [str(target)])
        self.assertEqual([item["url"] for item in updates], [str(target)])

    def test_directories_are_resolved_before_generic_document_connector(self) -> None:
        from warframe_lore.v1.scraper.collect.adapters import collect_pages

        pages = collect_pages(
            {"id": "src-local", "kind": "website", "location": str(self.root)},
            _Client(),
            {"expand_manifests": False},
        )
        self.assertEqual(len(pages), 4)
        self.assertTrue(
            all(page.title.endswith((".json", ".jsonl", ".md")) for page in pages)
        )


if __name__ == "__main__":
    unittest.main()
