"""Magasin d'activité membre persistant (SQLite) : compteur, fenêtre récente
et persistance à travers les redémarrages."""

from __future__ import annotations

import os
import tempfile
import unittest

from warframe_lore.discord.activity import MemberActivityStore


class MemberActivityStoreTests(unittest.TestCase):
    def test_record_count_recent(self):
        store = MemberActivityStore(":memory:")
        store.record(1, "premier")
        store.record(1, "second")
        store.record(2, "autre")
        self.assertEqual(store.count(1), 2)
        self.assertEqual(store.count(2), 1)
        self.assertEqual(store.recent(1), ["premier", "second"])
        self.assertEqual(store.all_counts(), {1: 2, 2: 1})

    def test_fenetre_recente_bornée(self):
        store = MemberActivityStore(":memory:", keep_last=3)
        for i in range(6):
            store.record(1, f"msg {i}")
        # Le compteur total garde tout ; la fenêtre ne garde que les 3 derniers.
        self.assertEqual(store.count(1), 6)
        self.assertEqual(store.recent(1), ["msg 3", "msg 4", "msg 5"])

    def test_persiste_across_restarts(self):
        path = os.path.join(tempfile.mkdtemp(), "activity.db")
        first = MemberActivityStore(path)
        first.record(7, "bonjour")
        first.record(7, "encore")
        first.close()

        second = MemberActivityStore(path)
        self.assertEqual(second.count(7), 2)
        self.assertEqual(second.recent(7), ["bonjour", "encore"])
        second.close()


if __name__ == "__main__":
    unittest.main()
