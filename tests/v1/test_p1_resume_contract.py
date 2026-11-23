"""P1 checkpoint resume contract."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from warframe_lore.v1.scraper.storage import write_json
from warframe_lore.v1.scraper.use_cases.run_controls import RunControl
from warframe_lore.v1.scraper.use_cases.run_universe import run_universe


class _Obs:
    def progress(self, *_a, **_k):
        pass

    def log(self, *_a, **_k):
        pass

    def event(self, *_a, **_k):
        pass


class _Snapshot:
    def __init__(self):
        self.sources_by_uid = {
            "u1": [
                {"id": "s1", "location": "https://a.test", "status": "active"},
                {"id": "s2", "location": "https://b.test", "status": "active"},
            ]
        }
        self.candidates_by_uid = {"u1": []}
        self.capabilities_by_uid = {}


class _Ctx:
    def __init__(self, base: Path):
        self.client = object()
        self.export_root = base / "exports"
        self.snapshot = _Snapshot()
        self.state: dict[str, Any] = {}
        self.observer = _Obs()
        self.control = RunControl()
        self.checkpoint_path = base / "run_checkpoint.json"


class ResumeTests(unittest.TestCase):
    def test_resume_skips_completed_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_json(base / "run_checkpoint.json", {
                "universe_id": "u1",
                "last_source_index": 1,
                "status": "cancelled",
            })
            ctx = _Ctx(base)
            calls: list[str] = []

            import sys
            mod = sys.modules["warframe_lore.v1.scraper.use_cases.async_collect"]
            old = mod.collect_source

            def fake_collect(source, _uid, _client, _limits, _state):
                calls.append(str(source["id"]))
                return [], [], []

            mod.collect_source = fake_collect  # type: ignore[assignment]
            try:
                out = run_universe(
                    cast(Any, ctx),
                    {"id": "u1", "name": "U"},
                    ["json"],
                    {"rag_coupling": False},
                )
            finally:
                mod.collect_source = old  # type: ignore[assignment]
            self.assertEqual(calls, ["s2"])
            self.assertFalse(out.get("cancelled"))
