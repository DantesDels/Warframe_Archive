"""Timeline domain: lazy hierarchy + paradox edges + API payloads."""

from __future__ import annotations

import unittest

from warframe_lore.timeline import (
    all_edges,
    all_nodes,
    children,
    children_payload,
    edges,
    graph_payload,
    node,
    paradox_edges,
    roots,
    roots_payload,
    sequel_edges,
)


class TimelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.roots = roots()
        self.nodes = {n["id"]: n for n in all_nodes()}

    def test_roots_are_arenas_with_children(self) -> None:
        self.assertTrue(self.roots, "au moins une ère racine")
        for r in self.roots:
            self.assertEqual(r["type"], "era")
            self.assertIsNone(r["parent_id"])
            self.assertTrue(r["has_children"])

    def test_empire_orokin_divise(self) -> None:
        """L'Empire Orokin racine se divise : Ancienne Guerre (chemin
        principal) et Zariman (branche paradoxale) — jamais séquentiels."""
        self.assertIn("era-orokin", self.nodes)
        self.assertEqual(self.nodes["era-old-war"]["parent_id"], "era-orokin")
        self.assertEqual(self.nodes["era-zariman"]["parent_id"], "era-orokin")
        self.assertEqual(self.nodes["era-origin"]["parent_id"], "era-old-war")
        self.assertEqual(self.nodes["q-zariman"]["parent_id"], "era-zariman")

    def test_causalite_origin(self) -> None:
        """Octavia's Anthem suit The War Within, The Sacrifice en découle,
        tous deux dans le Système d'Origine."""
        self.assertEqual(self.nodes["q-octavia"]["parent_id"], "era-origin")
        self.assertEqual(self.nodes["q-sacrifice"]["parent_id"], "era-origin")

    def test_hierarchie_validite(self) -> None:
        for node_id, n in self.nodes.items():
            if n["parent_id"] is not None:
                parent = self.nodes.get(n["parent_id"])
                self.assertIsNotNone(parent, f"parent inconnu: {node_id}")
                if n["type"] == "fragment":
                    # Les fragments pendent sous une quête OU sous une ère
                    # fusionnée (node-1999, node-duviri).
                    expected_type = ("quest", "era")
                else:
                    # Toute autre entité (era, quest, character,
                    # warframe-lore) pend sous une ère OU une quête.
                    expected_type = ("era", "quest")
                self.assertIn(parent["type"], expected_type,
                              f"parent de {node_id} mal classifié")
            # Un noeud sans enfant n'expose jamais has_children=True.
            if n["type"] == "fragment":
                self.assertFalse(n["has_children"])

    def test_doublons_fusionnes(self) -> None:
        """1999 et Duviri sont fusionnés (ère + quête) : un seul nœud par
        monde, aucun doublon laissé derrière."""
        for gone in ("era-1999", "q-1999", "era-duviri", "q-duviri"):
            self.assertNotIn(gone, self.nodes, f"doublon encore présent: {gone}")
        for merged in ("node-1999", "node-duviri"):
            self.assertEqual(self.nodes[merged]["type"], "era")
            self.assertIsNone(self.nodes[merged]["parent_id"])
        self.assertEqual(self.nodes["f-1999-hollvania"]["parent_id"], "node-1999")
        self.assertEqual(self.nodes["f-1999-indifference"]["parent_id"], "node-1999")
        self.assertEqual(self.nodes["f-hex-kim"]["parent_id"], "q-hex")
        self.assertEqual(self.nodes["f-duviri-throne"]["parent_id"], "node-duviri")
        self.assertEqual(self.nodes["f-duviri-thrax"]["parent_id"], "node-duviri")

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
        kids = children("q-second")
        self.assertTrue(kids)
        types = {k["type"] for k in kids}
        self.assertIn("fragment", types)
        self.assertIn("character", types)
        self.assertEqual(
            {f["id"] for f in kids if f["type"] == "fragment"},
            {"f-second-sentients", "f-second-margulis"},
        )

    def test_paradox_edges_points_existants(self) -> None:
        for edge in all_edges():
            for endpoint in (edge["source"], edge["target"]):
                self.assertIn(endpoint, self.nodes,
                              f"edge -> noeud inconnu: {endpoint}")

    def test_causalite_edges(self) -> None:
        """Chaîne causale within -> octavia -> sacrifice (paradox=False),
        et burst Zariman -> Duviri/1999 (paradox=True)."""
        seq = {(e["source"], e["target"]) for e in sequel_edges()}
        self.assertIn(("q-within", "q-octavia"), seq)
        self.assertIn(("q-octavia", "q-sacrifice"), seq)
        par = {(e["source"], e["target"]) for e in paradox_edges()}
        self.assertIn(("era-zariman", "node-duviri"), par)
        self.assertIn(("era-zariman", "node-1999"), par)
        # 1999 et Duviri ne sont plus liés séquentiellement.
        self.assertNotIn(("node-1999", "node-duviri"), par | seq)
        self.assertNotIn(("q-1999", "q-duviri"), par | seq)

    def test_roots_payload(self) -> None:
        payload = roots_payload()
        self.assertEqual(payload["nodes"], self.roots)
        self.assertEqual(payload["edges"], edges())

    def test_children_payload(self) -> None:
        payload = children_payload("node-1999")
        self.assertIsNotNone(payload)
        self.assertTrue(payload["nodes"])
        self.assertEqual(payload["edges"], [])
        self.assertEqual(
            {f["id"] for f in children_payload("node-1999")["nodes"]},
            {"q-hex", "f-1999-hollvania", "f-1999-indifference"},
        )
        self.assertEqual(len(children_payload("era-origin")["edges"]), 3)
        self.assertEqual(
            {e["source"] for e in children_payload("era-orokin")["edges"]},
            {"era-orokin", "era-zariman"},
        )
        self.assertIsNone(children_payload("inconnu"))

    def test_ids_uniques(self) -> None:
        ids = [n["id"] for n in all_nodes()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_node_internal(self) -> None:
        self.assertEqual(node("node-duviri")["type"], "era")
        self.assertIsNone(node("absent"))

    def test_codex_slugs(self) -> None:
        for n in all_nodes():
            self.assertIn("codex_slug", n)
        self.assertEqual(self.nodes["era-orokin"]["codex_slug"], "empire-orokin")
        self.assertEqual(self.nodes["c-albrecht"]["codex_slug"], "albrecht-entrati")
        self.assertEqual(self.nodes["wf-gara"]["codex_slug"], "gara")
        # Les fragments ne sont pas encore référencés au codex.
        self.assertIsNone(self.nodes["f-harrow-rell"]["codex_slug"])

    def test_personnages_et_lore_warframes(self) -> None:
        by_id = {n["id"]: n for n in all_nodes()}
        chars = {n["id"] for n in all_nodes() if n["type"] == "character"}
        self.assertIn("c-ballas", chars)
        self.assertIn("c-lotus", chars)
        self.assertEqual(by_id["c-lotus"]["parent_id"], "q-second")
        wf = {n["id"] for n in all_nodes() if n["type"] == "warframe-lore"}
        self.assertEqual(
            wf, {"wf-umbra", "wf-inaros", "wf-gara"},
            "Inaros/Gara/Umbra tissent le lore des Warframes",
        )
        # Inaros et Gara sont liés à leurs ères.
        self.assertEqual(by_id["wf-inaros"]["parent_id"], "era-origin")
        self.assertEqual(by_id["wf-gara"]["parent_id"], "era-origin")
        self.assertEqual(by_id["wf-umbra"]["parent_id"], "q-sacrifice")

    def test_aucune_arme(self) -> None:
        lower = [n["label"].lower() for n in all_nodes()] + [
            " ".join(x["label"].lower().split()) for x in all_edges() if x.get("label")
        ]
        joined = " ".join(lower)
        for prohibited in ("arma", "lame", "canon"):
            self.assertNotIn(prohibited, joined)

    def test_graph_payload(self) -> None:
        payload = graph_payload()
        self.assertEqual(len(payload["nodes"]), len(self.nodes))
        self.assertEqual(len(payload["edges"]), len(all_edges()))
        for n in payload["nodes"]:
            for key in ("id", "type", "label", "codex_slug", "expanded",
                        "parent_id", "year", "note", "has_children"):
                self.assertIn(key, n)
            self.assertIs(False, n["expanded"])
        kinds = {n["type"] for n in payload["nodes"]}
        self.assertEqual(kinds, {"era", "quest", "character", "warframe-lore",
                                 "fragment"})
        for e in payload["edges"]:
            self.assertIn(e["type"], ("canonical", "paradox"))
            self.assertIn(e["source"], self.nodes)
            self.assertIn(e["target"], self.nodes)


if __name__ == "__main__":
    unittest.main()