"""P1 bounded async scheduler contracts."""

from __future__ import annotations

import asyncio
import unittest
from typing import Any, cast

from warframe_lore.v1.scraper.use_cases.async_collect import collect_sources_async
from warframe_lore.v1.scraper.use_cases.run_controls import RunControl


class _Obs:
    def progress(self, *_a, **_k):
        pass

    def log(self, *_a, **_k):
        pass

    def event(self, *_a, **_k):
        pass


class _Ctx:
    def __init__(self):
        self.client = object()
        self.state: dict[str, Any] = {}
        self.observer = _Obs()
        self.control = RunControl()


class AsyncSchedulerTests(unittest.TestCase):
    def test_collects_and_checkpoints(self):
        ctx = _Ctx()
        sources = [
            {"id": "s1", "location": "https://a.test/1"},
            {"id": "s2", "location": "https://b.test/2"},
        ]
        checkpoints: list[str] = []

        import warframe_lore.v1.scraper.use_cases.async_collect as mod
        old = mod.collect_source

        def fake_collect(source, _uid, _client, limits, _state):
            limits.setdefault("pending_child_urls", [])
            return (
                [{"id": source["id"], "title": "t", "url": source["location"]}],
                [],
                [],
            )

        mod.collect_source = fake_collect  # type: ignore[assignment]
        try:
            docs, errs, pending, cancelled = asyncio.run(
                collect_sources_async(
                    cast(Any, ctx),
                    sources,
                    "u1",
                    {
                        "max_concurrency": 2,
                        "per_host_concurrency": 1,
                        "max_retries": 0,
                    },
                    resume_completed=set(),
                    checkpoint_cb=lambda *_a: checkpoints.append("x"),
                    progress_cb=lambda *_a: None,
                )
            )
        finally:
            mod.collect_source = old  # type: ignore[assignment]

        self.assertFalse(cancelled)
        self.assertEqual(len(docs), 2)
        self.assertEqual(errs, [])
        self.assertEqual(pending, [])
        self.assertTrue(checkpoints)

    def test_retries_then_succeeds(self):
        ctx = _Ctx()
        calls = {"n": 0}
        import warframe_lore.v1.scraper.use_cases.async_collect as mod
        old = mod.collect_source

        def flaky(source, _uid, _client, limits, _state):
            limits.setdefault("pending_child_urls", [])
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return (
                [{"id": source["id"], "title": "t", "url": source["location"]}],
                [],
                [],
            )

        mod.collect_source = flaky  # type: ignore[assignment]
        try:
            docs, errs, _p, cancelled = asyncio.run(
                collect_sources_async(
                    cast(Any, ctx),
                    [{"id": "s1", "location": "https://a.test"}],
                    "u1",
                    {
                        "max_concurrency": 1,
                        "per_host_concurrency": 1,
                        "max_retries": 1,
                        "per_host_delay": 0,
                    },
                    resume_completed=set(),
                    checkpoint_cb=lambda *_a: None,
                    progress_cb=lambda *_a: None,
                )
            )
        finally:
            mod.collect_source = old  # type: ignore[assignment]
        self.assertFalse(cancelled)
        self.assertEqual(len(docs), 1)
        self.assertEqual(errs, [])
