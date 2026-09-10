"""Timeline domain: lazy hierarchy + paradox edges + API payloads."""

from __future__ import annotations

import unittest

from warframe_lore.timeline import (
    all_nodes,
    children,
    children_payload,
    node,
    paradox_edges,
    roots,
    roots_payload,
)


class TimelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.roots = roots()
        self.nodes = {n["id"]: n for n in all_nodes()}

    def test_roots_are_arenas_with_children(self) -> None:
        self.assertTrue(self.roots, "au moins une ère racine")
        for r in self.roots:
            self.assertEqual(r["kind"], "era")
            self.assertIsNone(r["parent_id"])
            self.assertTrue(r["has_children"])

    def test_hierarchie_validite(self) -> None:
        for node_id, n in self.nodes.items():
            if n["parent_id"] is not None:
                parent = self.nodes.get(n["parent_id"])
                self.assertIsNotNone(parent, f"parent inconnu: {node_id}")
                expected_kind = "era" if n["kind"] == "quest" else "quest"
                self.assertEqual(parent["kind"], expected_kind,
                                 f"parent de {node_id} mal classifié")
            # Un noeud sans enfant n'expose jamais has_children=True.
            if n["kind"] == "fragment":
                self.assertFalse(n["has_children"])

    def test_has_children_coherent_avec_arbre(self) -> None:
        parents = {n["parent_id"] for n in all_nodes() if n["parent_id"]}
        for node_id, n in self.nodes.items():
            self.assertEqual(n["has_children"], node_id in parents,
                             f"has_children incohérent: {node_id}")

    def test_children_du_parent(self) -> None:
        quests = children("era-origin")
        self.assertTrue(quests)
        ids = {q["id"] for q in quests}
        self.assertIn("q-second", ids)
        self.assertIn("q-new-war", ids)
        self.assertNotIn("era-duviri", ids)

    def test_children_inconnu_vaut_none(self) -> None:
        self.assertIsNone(children("nimporte-quoi"))

    def test_grand_parent_fragments(self) -> None:
        frags = children("q-second")
        self.assertTrue(frags)
        self.assertTrue(all(f["kind"] == "fragment" for f in frags))

    def test_paradox_edges_points_existants(self) -> None:
        for edge in paradox_edges():
            for endpoint in (edge["source"], edge["target"]):
                self.assertIn(endpoint, self.nodes,
                              f"edge paradox -> noeud inconnu: {endpoint}")

    def test_roots_payload(self) -> None:
        payload = roots_payload()
        self.assertEqual(payload["nodes"], self.roots)
        self.assertEqual(len(payload["edges"]), len(paradox_edges()))

    def test_children_payload(self) -> None:
        payload = children_payload("era-1999")
        self.assertIsNotNone(payload)
        self.assertTrue(payload["nodes"])
        self.assertEqual(payload["edges"], [])
        self.assertIsNone(children_payload("inconnu"))

    def test_ids_uniques(self) -> None:
        ids = [n["id"] for n in all_nodes()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_node_internal(self) -> None:
        self.assertEqual(node("q-duviri")["kind"], "quest")
        self.assertIsNone(node("absent"))


if __name__ == "__main__":
    unittest.main()