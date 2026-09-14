"""Optional read-only mirror audit, separate from the autonomous test suite.

Run: python -B -m unittest discover -s tests -p audit_kim_dm.py -v
"""

import json
import unittest
from collections import Counter
from pathlib import Path

from warframe_lore.kim_dm import WIKI_PAGE_MAP, KimDM, parse_dialogue_file

MIRROR = Path(__file__).resolve().parents[1] / "out" / "kim_dm"
ENGINE = "/EE/Types/Engine/"


@unittest.skipUnless((MIRROR / "data").is_dir()
                     and (MIRROR / "dicts" / "en.json").is_file(),
                     "Local KIM mirror is not installed")
class LocalMirrorAudit(unittest.TestCase):
    def test_all_native_graphs_against_raw_reachability_and_route_multiplicity(self):
        dict_path = MIRROR / "dicts" / "en.json"
        kim_dict = json.loads(dict_path.read_text(encoding="utf-8"))
        totals = Counter()
        node_types = Counter()
        files = sorted((MIRROR / "data").glob("*.dialogue.json"))
        self.assertTrue(files)
        for path in files:
            with self.subTest(file=path.name):
                raw = json.loads(path.read_text(encoding="utf-8"))
                index = {n["Id"]: n for n in raw}
                self.assertEqual(len(index), len(raw), "Duplicate native IDs")
                self.assertTrue(all(type(nid) is int for nid in index))
                starts = [n for n in raw if n["type"] == ENGINE + "StartDialogueNode"]
                sender = next((wiki for wiki, stem in WIKI_PAGE_MAP.items()
                               if path.name == f"{stem}Dialogue_rom.dialogue.json"),
                              path.name.removesuffix("Dialogue_rom.dialogue.json"))
                conversations = parse_dialogue_file(raw, kim_dict, sender)
                self.assertEqual(len(conversations), len(starts))
                by_root = {c["graph"]["rootId"]: c for c in conversations}
                self.assertEqual(len(by_root), len(starts))
                raw_edges = {}
                for nid, item in index.items():
                    routes = [(route, None, item.get(route, []), label)
                              for route, label in (("Outgoing", ""),
                                                   ("TrueNodes", "True"),
                                                   ("FalseNodes", "False"))]
                    for output_index, output in enumerate(item.get("Outputs", [])):
                        expression = output.get("Expression", "")
                        routes.append(
                            ("Outputs", output_index,
                             output.get("Outgoing", []),
                             kim_dict.get(expression, expression)))
                    raw_edges[nid] = []
                    for route, output_index, targets, label in routes:
                        for target in targets:
                            if type(target) is int and target in index:
                                raw_edges[nid].append((f"dm{nid}", f"dm{target}", route,
                                                       output_index, label))
                            else:
                                totals["missing_refs"] += 1
                for start in starts:
                    conversation = by_root[f"dm{start['Id']}"]
                    graph = conversation["graph"]
                    reachable = set()
                    expected_edges = Counter()
                    stack = [start["Id"]]
                    while stack:
                        current = stack.pop()
                        if current in reachable:
                            continue
                        reachable.add(current)
                        expected_edges.update(raw_edges[current])
                        stack.extend(int(edge[1][2:]) for edge in raw_edges[current])
                    self.assertEqual({n["id"] for n in graph["nodes"]},
                                     {f"dm{nid}" for nid in reachable})
                    self.assertEqual(len(graph["nodes"]), len(reachable))
                    self.assertEqual(Counter((e["source"], e["target"], e["route"],
                                              e.get("outputIndex"), e["label"])
                                             for e in graph["edges"]), expected_edges)
                    edge_ids = {e["id"] for e in graph["edges"]}
                    self.assertEqual(len(edge_ids), len(graph["edges"]))
                    start_nodes = [n["id"] for n in graph["nodes"]
                                   if n["kind"] == "start"]
                    self.assertEqual(start_nodes, [graph["rootId"]])
                    self.assertEqual(graph["nodes"][0]["text"],
                                     kim_dict.get(start["Content"], start["Content"]))
                    for visible in graph["nodes"]:
                        item = index[int(visible["id"][2:])]
                        self.assertEqual(visible["type"], item["type"])
                        if visible["kind"] in ("npc", "choice"):
                            key = item.get("LocTag") or item.get("Content") or ""
                            self.assertEqual(visible["text"], kim_dict.get(key, key))
                            speaker = item.get("Speaker") or ""
                            is_choice = visible["kind"] == "choice"
                            expected_speaker = ("Vous" if is_choice else
                                                kim_dict.get(speaker, speaker)
                                                or sender)
                            self.assertEqual(visible["speaker"], expected_speaker)
                        elif visible["kind"] == "chemistry":
                            self.assertEqual(visible["chemistryDelta"],
                                             item.get("ChemistryDelta", 0))
                        else:
                            self.assertTrue(visible["text"])
                        if item["type"] in (ENGINE + "CheckBooleanScriptDialogueNode",
                                            ENGINE + "ScriptDialogueNode"):
                            for field in ("Script", "Function"):
                                key = item["Script"][field]
                                self.assertIn(kim_dict.get(key, key), visible["text"])
                    spoken = {(n["speaker"], n["text"], n["player"])
                              for n in graph["nodes"] if n["kind"] in ("npc", "choice")}
                    for line in conversation["messages"]:
                        spoken_line = (line["speaker"], line["text"],
                                       line["player"])
                        self.assertIn(spoken_line, spoken)
                    for step in conversation["script"]:
                        self.assertIn(step["kind"], ("npc", "prompt"))
                        if step["kind"] == "npc":
                            self.assertIn(
                                (step["speaker"], step["text"], False), spoken)
                    totals["graph_nodes"] += len(graph["nodes"])
                    totals["graph_edges"] += len(graph["edges"])
                totals["files"] += 1
                totals["conversations"] += len(conversations)
                totals["raw_nodes"] += len(raw)
                node_types.update(n["type"].removeprefix(ENGINE) for n in raw)
                print(f"{path.name}: {len(conversations)} conversations, "
                      f"{len(raw)} native nodes")

        dm = KimDM(MIRROR / "data", MIRROR / "dicts")
        for wiki in WIKI_PAGE_MAP:
            summaries = dm.conversations_for(wiki)
            if summaries is None:
                continue
            graph = dm.graph(wiki)
            self.assertEqual(graph["rootId"], "root")
            expected_nodes = {}
            expected_edges = {}
            expected_roots = set()
            for summary in summaries:
                individual = dm.graph(wiki, summary["id"])
                expected_roots.add(individual["rootId"])
                expected_nodes.update((n["id"], n) for n in individual["nodes"])
                expected_edges.update((e["id"], e) for e in individual["edges"])
            self.assertEqual({n["id"]: n for n in graph["nodes"] if n["id"] != "root"},
                             expected_nodes)
            real_edges = {e["id"]: e for e in graph["edges"]
                          if e["source"] != "root"}
            self.assertEqual(real_edges, expected_edges)
            root_targets = {e["target"] for e in graph["edges"]
                            if e["source"] == "root"}
            self.assertEqual(root_targets, expected_roots)
            self.assertEqual(len(graph["edges"]),
                             len({e["id"] for e in graph["edges"]}))
        if dm.conversations_for("Amir") is not None:
            print(f"Amir via Jabir: {len(dm.conversations_for('Amir'))} conversations")
        print("Audit totals:", dict(totals))
        print("Native types:", dict(sorted(node_types.items())))


if __name__ == "__main__":
    unittest.main()
