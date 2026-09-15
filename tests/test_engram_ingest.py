"""ENGRAM ETL mapping tests: provenance, KIM detection, upsert kwargs."""

from __future__ import annotations

import unittest

from warframe_lore.engram.scripts.ingest import (
    _is_kim_page,
    _page_source_url,
    _upsert_kwargs,
)


class PageSourceUrlTests(unittest.TestCase):
    def test_site_route_builds_from_path_title(self):
        self.assertEqual(
            _page_source_url({
                "_source": "https://www.warframe.com",
                "page_title": "/fr/game/warframes/saryn",
            }),
            "https://www.warframe.com/fr/game/warframes/saryn",
        )

    def test_wiki_title_builds_from_base(self):
        self.assertEqual(
            _page_source_url({
                "_source": "https://wiki.warframe.com/wiki/",
                "page_title": "Saryn/Main",
            }),
            "https://wiki.warframe.com/wiki/Saryn/Main",
        )

    def test_missing_provenance_returns_empty(self):
        self.assertEqual(_page_source_url({}), "")
        self.assertEqual(_page_source_url({"page_title": "/fr"}), "")

    def test_canonical_source_is_kept_as_is(self):
        self.assertEqual(
            _page_source_url({
                "_source": "https://www.warframe.com/fr/game/warframes/nyx",
                "page_title": "/fr/game/warframes/nyx",
            }),
            "https://www.warframe.com/fr/game/warframes/nyx",
        )
        self.assertEqual(
            _page_source_url({
                "_source": "https://wiki.warframe.com/wiki/Acrithis",
                "page_title": "Acrithis",
            }),
            "https://wiki.warframe.com/wiki/Acrithis",
        )


class IsKimPageTests(unittest.TestCase):
    def test_bucket_id_wins(self):
        self.assertTrue(_is_kim_page(
            {"bucket_id": "Lore_Dialogues_KIM", "category": "Quotes"}))
        self.assertFalse(_is_kim_page(
            {"bucket_id": "Lore_Characters", "category": "Discussions KIM"}))

    def test_legacy_category_fallback(self):
        self.assertTrue(_is_kim_page({"category": "Discussions KIM & Fables"}))
        self.assertFalse(_is_kim_page({"category": "Personnages"}))


class UpsertKwargsTests(unittest.TestCase):
    def test_category_prefers_bucket_id_and_source_url_is_kept(self):
        kwargs = _upsert_kwargs({
            "page_title": "/fr/updates",
            "_pageid": 1297496930,
            "_source": "https://www.warframe.com",
            "bucket_id": "Lore_Site_Officiel_FR",
            "category": "Site officiel (FR)",
            "content_markdown": "Contenu.",
            "sections": [{"section": "x"}],
        }, is_kim=False)
        self.assertEqual(kwargs["category"], "Lore_Site_Officiel_FR")
        self.assertEqual(kwargs["source_url"],
                         "https://www.warframe.com/fr/updates")
        self.assertEqual(kwargs["page_id"], 1297496930)

    def test_kim_page_ignores_sections(self):
        kwargs = _upsert_kwargs({
            "page_title": "KIM",
            "_pageid": 1,
            "bucket_id": "Lore_Dialogues_KIM",
            "category": "Discussions KIM",
            "content_markdown": "foo",
            "sections": [{"section": "x"}],
        }, is_kim=True)
        self.assertIsNone(kwargs["sections"])
        self.assertTrue(kwargs["detect_kim_dialogues"])


if __name__ == "__main__":
    unittest.main()
