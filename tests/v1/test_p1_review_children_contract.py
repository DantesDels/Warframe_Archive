"""P1 human-in-the-loop child review contract."""

from __future__ import annotations

import unittest

from warframe_lore.v1.scraper.UI import WorkshopWorkspace
from warframe_lore.v1.scraper.use_cases.review_children import preview_child_candidates


class _Resp:
    def __init__(self, url: str, content: bytes):
        self.url = url
        self.content = content
        self.encoding = "utf-8"
        self.status = 200


class _Client:
    def get(self, _url: str, **_kwargs):
        body = (
            b'<html><body><a href="https://example.org/a"></a>'
            b'<a href="/b"></a></body></html>'
        )
        return _Resp("https://example.org/root", body)


class ReviewChildrenTests(unittest.TestCase):
    def test_preview_adds_child_candidates_as_proposed(self):
        ws = WorkshopWorkspace()
        ws.create("Warframe")
        universe = ws.get("warframe")
        assert universe is not None
        added = preview_child_candidates(
            ws, universe, "https://example.org/root", client=_Client()
        )
        self.assertTrue(added)
        cands = ws.candidates_for("warframe")
        self.assertTrue(any(c.get("discoveredBy") == "manifest_review" for c in cands))
        self.assertTrue(all(c.get("status") == "proposed" for c in added))


if __name__ == "__main__":
    unittest.main()
