"""Native KIM contracts, using only in-memory data and temporary fixtures."""

import copy
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from warframe_lore.kim_dm import KimDM, _anchor_graph, parse_dialogue_file


ENGINE = "/EE/Types/Engine/"


def node(node_id, node_type, **fields):
    return {"Id": node_id, "type": ENGINE + node_type, **fields}


class NativeDialogueTests(unittest.TestCase):
    def test_exact_types_and_false_start_suffixes(self):
        lookalikes = [
            "StartDialogueNode",
            "/Other/StartDialogueNode",
            ENGINE + "FakeStartDialogueNode",
            ENGINE + "StartDialogueNodeExtra",
            ENGINE + "startDialogueNode",
            "/Other/DialogueNode",
            "/Other/PlayerChoiceDialogueNode",
            "/Other/ChemistryDialogueNode",
            "/Other/EndDialogueNode",
            "/Other/SetBooleanDialogueNode",
        ]
        fake_nodes = [{"Id": index, "type": name, "Content": "Not a start"}
                      for index, name in enumerate(lookalikes)]
        self.assertEqual(parse_dialogue_file(fake_nodes, {}), [])
        native = [node(100, "StartDialogueNode", Content="OfficialRank2Title",
                       Outgoing=list(range(len(fake_nodes))))] + fake_nodes
        conversations = parse_dialogue_file(native, {})
        self.assertEqual(len(conversations), 1)
        conversation = conversations[0]
        self.assertEqual(conversation["title"], "OfficialRank2Title")
        self.assertEqual(conversation["rank"], "Rank 2")
        self.assertEqual(conversation["source"], "dm")
        graph = conversation["graph"]
        self.assertEqual(graph["rootId"], "dm100")
        self.assertEqual(graph["nodes"][0]["type"], ENGINE + "StartDialogueNode")
        self.assertEqual(graph["nodes"][0]["text"], "OfficialRank2Title")
        self.assertNotIn("root", {item["id"] for item in graph["nodes"]})
        for item, name in zip(graph["nodes"][1:], lookalikes):
            with self.subTest(node_type=name):
                self.assertEqual(item["type"], name)
                self.assertEqual(item["kind"], "system")
                self.assertIn("System action:", item["text"])
                self.assertIn("Not a start", item["text"])
                self.assertFalse(item["terminal"])
                self.assertFalse(item["player"])
        self.assertEqual(conversation["messages"], [])
        self.assertEqual(conversation["script"], [])

    def test_shuffled_sparse_native_ids_and_no_inferred_edges(self):
        native = [
            node(8000, "EndDialogueNode"),
            node(12, "DialogueNode", Content="Unreachable", Incoming=[900]),
            node(42, "PlayerChoiceDialogueNode", Content="Also unreachable",
                 Incoming=[0]),
            node(0, "DialogueNode", Content="Hello", Outgoing=[8000],
                 choices=[42]),
            node(900, "StartDialogueNode", Content="Sparse", Outgoing=[0]),
        ]
        original = copy.deepcopy(native)
        conversation = parse_dialogue_file(native, {}, sender="Amir")[0]
        self.assertEqual(native, original)
        graph = conversation["graph"]
        self.assertEqual(graph["rootId"], "dm900")
        self.assertEqual([item["id"] for item in graph["nodes"]],
                         ["dm900", "dm0", "dm8000"])
        self.assertEqual([(edge["source"], edge["target"])
                          for edge in graph["edges"]],
                         [("dm900", "dm0"), ("dm0", "dm8000")])
        self.assertEqual(conversation, parse_dialogue_file(
            list(reversed(native)), {}, sender="Amir")[0])

    def test_no_non_native_envelopes_or_id_coercion(self):
        start = node(90, "StartDialogueNode", Content="Native",
                     Outgoing=[0, "1", True, 1.0, 404])
        native = [start, node(0, "DialogueNode", Content="Zero"),
                  node("1", "StartDialogueNode", Content="String ID"),
                  node(True, "StartDialogueNode", Content="Boolean ID"),
                  {"type": ENGINE + "StartDialogueNode", "Content": "No ID"},
                  node(2, "DialogueNode", Content="Unreachable")]
        for wrapped in ({"Nodes": native}, {"nodes": native}, {"90": start}, None):
            with self.subTest(wrapped_type=type(wrapped)):
                self.assertEqual(parse_dialogue_file(wrapped, {}), [])
        conversations = parse_dialogue_file(native, {})
        self.assertEqual(len(conversations), 1)
        self.assertEqual({item["id"] for item in conversations[0]["graph"]["nodes"]},
                         {"dm90", "dm0"})

    def test_all_native_routes_preserve_parallel_edges_and_output_indices(self):
        native = [
            node(90, "StartDialogueNode", Content="Branches", Outgoing=[3]),
            node(3, "CheckBooleanDialogueNode", Content="Flag",
                 Outgoing=[5, 5], TrueNodes=[5, 4], FalseNodes=[5], Outputs=[
                     {"Expression": "/expr", "Outgoing": [5, 5]},
                     {"Expression": "/expr", "Outgoing": [5]},
                     {"Expression": "missing", "Outgoing": [404]},
                     {"Expression": "false", "Outgoing": [4]},
                 ]),
            node(4, "EndDialogueNode"),
            node(5, "EndDialogueNode"),
        ]
        graph = parse_dialogue_file(native, {"/expr": "x >= 2"})[0]["graph"]
        outgoing = [edge for edge in graph["edges"] if edge["source"] == "dm3"]
        actual = Counter((edge["target"], edge["route"], edge["label"],
                          edge.get("outputIndex")) for edge in outgoing)
        self.assertEqual(actual, Counter({
            ("dm5", "Outgoing", "", None): 2,
            ("dm5", "TrueNodes", "True", None): 1,
            ("dm4", "TrueNodes", "True", None): 1,
            ("dm5", "FalseNodes", "False", None): 1,
            ("dm5", "Outputs", "x >= 2", 0): 2,
            ("dm5", "Outputs", "x >= 2", 1): 1,
            ("dm4", "Outputs", "false", 3): 1,
        }))
        self.assertEqual(len(graph["edges"]), len({e["id"] for e in graph["edges"]}))
        for edge in graph["edges"]:
            self.assertEqual("outputIndex" in edge, edge["route"] == "Outputs")
        self.assertEqual(graph, parse_dialogue_file(
            list(reversed(native)), {"/expr": "x >= 2"})[0]["graph"])

    def test_cycles_self_edges_and_missing_references(self):
        native = [
            node(30, "StartDialogueNode", Content="Cycle", Outgoing=[3, 404]),
            node(3, "DialogueNode", Content="One", Outgoing=[7]),
            node(7, "UnknownDialogueNode", Content="Action",
                 Outgoing=[7, 3, 30, 50, 405]),
            node(50, "EndDialogueNode", Outgoing=[50]),
            node(99, "DialogueNode", Content="Orphan", Incoming=[7]),
        ]
        conversation = parse_dialogue_file(native, {}, "Amir")[0]
        graph = conversation["graph"]
        self.assertEqual({item["id"] for item in graph["nodes"]},
                         {"dm30", "dm3", "dm7", "dm50"})
        self.assertEqual({(e["source"], e["target"]) for e in graph["edges"]},
                         {("dm30", "dm3"), ("dm3", "dm7"), ("dm7", "dm7"),
                          ("dm7", "dm3"), ("dm7", "dm30"), ("dm7", "dm50"),
                          ("dm50", "dm50")})
        self.assertEqual([line["text"] for line in conversation["messages"]], ["One"])
        self.assertEqual([step["text"] for step in conversation["script"]], ["One"])

    def test_each_start_has_its_own_reachable_graph_with_shared_tail(self):
        native = [
            node(10, "StartDialogueNode", Content="First", Outgoing=[12]),
            node(20, "StartDialogueNode", Content="Second", Outgoing=[22]),
            node(12, "DialogueNode", Content="First line", Outgoing=[99]),
            node(22, "DialogueNode", Content="Second line", Outgoing=[99]),
            node(99, "EndDialogueNode"),
        ]
        conversations = parse_dialogue_file(native, {})
        self.assertEqual([c["id"] for c in conversations], ["First", "Second"])
        for conversation, root, ids in zip(conversations, ("dm10", "dm20"),
                                           ({"dm10", "dm12", "dm99"},
                                            {"dm20", "dm22", "dm99"})):
            graph = conversation["graph"]
            self.assertEqual(graph["rootId"], root)
            self.assertEqual({n["id"] for n in graph["nodes"]}, ids)
            self.assertEqual([n["id"] for n in graph["nodes"] if n["kind"] == "start"],
                             [root])

    def test_chemistry_signed_positive_negative_and_zero(self):
        for delta in (20, -10, 0, 2.5):
            with self.subTest(delta=delta):
                native = [node(4, "StartDialogueNode", Content="Chem", Outgoing=[6]),
                          node(6, "ChemistryDialogueNode", ChemistryDelta=delta,
                               Outgoing=[9]), node(9, "EndDialogueNode")]
                conversation = parse_dialogue_file(native, {})[0]
                chemistry = conversation["graph"]["nodes"][1]
                self.assertEqual(chemistry["kind"], "chemistry")
                self.assertEqual(chemistry["type"], ENGINE + "ChemistryDialogueNode")
                self.assertEqual(chemistry["chemistryDelta"], delta)
                self.assertEqual(chemistry["text"], f"{delta:+} Chemistry")
                self.assertFalse(chemistry["player"])
                self.assertFalse(chemistry["terminal"])
                self.assertEqual(conversation["messages"], [])
                self.assertEqual(conversation["script"], [])

    def test_localization_preserves_text_and_translates_speakers_everywhere(self):
        kim_dict = {"/title": "Official title", "/line": " First  line\n\nSecond\r\n{P1}",
                    "/name": "Translated name", "/content": "Content\ntranslation",
                    "/choice": "Choice\ntranslation", "/fallback": "Wiki name"}
        native = [
            node(1, "StartDialogueNode", Content="/title", LocTag="Wrong title",
                 Outgoing=[2]),
            node(2, "DialogueNode", LocTag="/line", Content="Ignored",
                 Speaker="/name", Outgoing=[3]),
            node(3, "DialogueNode", Content="/content", Outgoing=[4]),
            node(4, "DialogueNode", Content="Literal\ntext", Speaker="Literal name",
                 Outgoing=[5]),
            node(5, "DialogueNode", LocTag="/untranslated", Speaker="/unknown-name",
                 Outgoing=[6]),
            node(6, "PlayerChoiceDialogueNode", Content="/choice", Speaker="/name",
                 Outgoing=[7]),
            node(7, "DialogueNode", LocTag="", Content="After", Speaker="",
                 Outgoing=[8]),
            node(8, "EndDialogueNode"),
        ]
        conversation = parse_dialogue_file(native, kim_dict, "/fallback")[0]
        self.assertEqual(conversation["id"], "/title")
        self.assertEqual(conversation["title"], "Official title")
        graph_nodes = {n["id"]: n for n in conversation["graph"]["nodes"]}
        self.assertEqual(graph_nodes["dm1"]["text"], "Official title")
        self.assertEqual(graph_nodes["dm2"]["locTag"], "/line")
        expected = [
            ("Translated name", kim_dict["/line"], False),
            ("Wiki name", kim_dict["/content"], False),
            ("Literal name", "Literal\ntext", False),
            ("/unknown-name", "/untranslated", False),
            ("Vous", kim_dict["/choice"], True),
            ("Wiki name", "After", False),
        ]
        self.assertEqual([(n["speaker"], n["text"], n["player"])
                          for n in conversation["graph"]["nodes"][1:-1]], expected)
        self.assertEqual([(n["speaker"], n["text"], n["player"])
                          for n in conversation["messages"]], expected)
        self.assertEqual([n["index"] for n in conversation["messages"]], list(range(1, 7)))
        npc_steps = [s for s in conversation["script"] if s["kind"] == "npc"]
        self.assertEqual([(s["speaker"], s["text"], s["player"]) for s in npc_steps],
                         [entry for entry in expected if not entry[2]])
        prompts = [s for s in conversation["script"] if s["kind"] == "prompt"]
        self.assertEqual(prompts[0]["options"],
                         [{"text": kim_dict["/choice"], "ends": False}])
        self.assertTrue(conversation["script"][-1]["ends"])

    def test_all_system_actions_remain_explicit_without_npc_messages(self):
        kim_dict = {"/flag": "Friend", "/script": "checks.lua", "/function": "Ready",
                    "/counter": "Trust", "/expr": "x >= 2", "/tag": "Other chat",
                    "/dialogue": "Other.dialogue", "/detail": "Action\ndetails",
                    "/sender": "System name"}
        actions = [
            ("CheckBooleanDialogueNode", {"Content": "/flag"}, "Check boolean: Friend"),
            ("CheckBooleanScriptDialogueNode",
             {"Script": {"Script": "/script", "Function": "/function"}},
             "Check script: checks.lua :: Ready"),
            ("ScriptDialogueNode",
             {"Script": {"Script": "/script", "Function": "/function"}},
             "Run script: checks.lua :: Ready"),
            ("CheckMultiBooleanDialogueNode",
             {"Outputs": [{"Expression": "/flag"}, {"Expression": "false"}]},
             "Check booleans\nFriend\nfalse"),
            ("SetBooleanDialogueNode", {"Content": "/flag"}, "Friend is now true"),
            ("ResetBooleanDialogueNode", {"Content": "/flag"}, "Friend is now false"),
            ("IncCounterDialogueNode", {"Content": "/counter 2"},
             "Increment counter: Trust +2"),
            ("IncCounterDialogueNode", {"Content": "/counter -3"},
             "Increment counter: Trust -3"),
            ("IncCounterDialogueNode", {"Content": "/counter 0"},
             "Increment counter: Trust +0"),
            ("CheckCounterDialogueNode",
             {"CounterName": "/counter", "Content": "Obsolete summary",
              "Outputs": [{"Expression": "/expr"}, {"Expression": "false"}]},
             "Check counter: Trust\nx >= 2\nfalse"),
            ("SpecialCompletionDialogueNode",
             {"CompletionType": 2, "OtherDialogueInfos": [
                 {"Tag": "/tag", "Dialogue": "/dialogue", "Value": 0},
                 {"Tag": "Second chat", "Dialogue": "Second.dialogue"}]},
             "Special completion (type 2)\nOther chat (Other.dialogue)\n"
             "Second chat (Second.dialogue)"),
            ("SpecialCompletionDialogueNode", {"CompletionType": 1},
             "Special completion (type 1)"),
            ("FutureDialogueNode", {"Content": "/detail", "Speaker": "/sender"},
             "System action: FutureDialogueNode\nAction\ndetails"),
            ("AnotherFutureDialogueNode", {"LocTag": "/detail"},
             "System action: AnotherFutureDialogueNode\nAction\ndetails"),
        ]
        native = [node(0, "StartDialogueNode", Content="Actions", Outgoing=[1])]
        for index, (name, fields, _) in enumerate(actions, 1):
            native.append(node(index, name, Outgoing=[index + 1], **fields))
        native.append(node(len(actions) + 1, "EndDialogueNode"))
        conversation = parse_dialogue_file(native, kim_dict, "Amir")[0]
        graph = conversation["graph"]
        self.assertEqual(len(graph["nodes"]), len(native))
        self.assertEqual(len(graph["edges"]), len(native) - 1)
        for item, (name, _, expected_text) in zip(graph["nodes"][1:-1], actions):
            with self.subTest(node_type=name):
                self.assertEqual(item["kind"], "system")
                self.assertEqual(item["type"], ENGINE + name)
                self.assertEqual(item["text"], expected_text)
                self.assertFalse(item["terminal"])
        self.assertEqual(graph["nodes"][-3]["speaker"], "System name")
        self.assertEqual(conversation["messages"], [])
        self.assertEqual(conversation["script"], [])

    def test_end_content_is_descriptive_not_an_inferred_conversation_edge(self):
        native = [
            node(0, "StartDialogueNode", Content="First", Outgoing=[1]),
            node(1, "EndDialogueNode", Content="/next", Outgoing=[3]),
            node(2, "StartDialogueNode", Content="/next"),
            node(3, "EndDialogueNode"),
        ]
        first = next(c for c in parse_dialogue_file(native, {"/next": "Next chat"})
                     if c["id"] == "First")
        graph = first["graph"]
        self.assertEqual([n["id"] for n in graph["nodes"]], ["dm0", "dm1", "dm3"])
        self.assertEqual(graph["nodes"][1]["text"], "Chat finished\nNext conversation: Next chat")
        self.assertEqual(graph["nodes"][2]["text"], "Chat finished")
        self.assertTrue(all(n["terminal"] for n in graph["nodes"][1:]))
        self.assertEqual(graph["edges"][-1]["target"], "dm3")

    def test_messages_dfs_and_script_first_branch_keep_existing_shapes(self):
        native = [
            node(0, "StartDialogueNode", Content="Script", Outgoing=[1]),
            node(1, "CheckBooleanDialogueNode", Content="Flag", TrueNodes=[2],
                 FalseNodes=[9]),
            node(2, "DialogueNode", LocTag="/hello", Speaker="/name", Outgoing=[3]),
            node(3, "SetBooleanDialogueNode", Content="Flag", LocTag="Not a message",
                 Outgoing=[4, 5]),
            node(4, "PlayerChoiceDialogueNode", LocTag="/choice1", Outgoing=[6]),
            node(5, "PlayerChoiceDialogueNode", Content="/choice2", Outgoing=[9]),
            node(6, "ChemistryDialogueNode", ChemistryDelta=10, Outgoing=[7]),
            node(7, "CheckMultiBooleanDialogueNode", Outputs=[
                {"Expression": "true", "Outgoing": [8]},
                {"Expression": "false", "Outgoing": [9]}]),
            node(8, "DialogueNode", Content="/reply", Outgoing=[10]),
            node(9, "DialogueNode", Content="Other branch", Outgoing=[10]),
            node(10, "EndDialogueNode"),
        ]
        kim_dict = {"/hello": "Hello\nthere", "/name": "Name", "/choice1": "First",
                    "/choice2": "Second", "/reply": "Reply"}
        conversation = parse_dialogue_file(native, kim_dict, "Amir")[0]
        self.assertEqual(conversation["script"], [
            {"kind": "npc", "speaker": "Name", "text": "Hello\nthere", "player": False,
             "ends": False, "jump_to": None},
            {"kind": "prompt", "options": [{"text": "First", "ends": False},
                                            {"text": "Second", "ends": False}],
             "ends": False, "jump_to": None},
            {"kind": "npc", "speaker": "Amir", "text": "Reply", "player": False,
             "ends": True, "jump_to": None},
        ])
        self.assertEqual([n["text"] for n in conversation["messages"]],
                         ["Hello\nthere", "First", "Reply", "Other branch", "Second"])
        # Contrat : chaque message porte aussi ``lines`` (une entrée par
        # réplique, découpée du texte multi-lignes pour l'affichage en liste).
        self.assertEqual([m["lines"] for m in conversation["messages"]],
                         [["Hello", "there"], ["First"], ["Reply"],
                          ["Other branch"], ["Second"]])
        for message in conversation["messages"]:
            self.assertEqual(set(message),
                             {"index", "speaker", "text", "player", "lines"})

    def test_start_choices_are_prompts_and_dead_ends_finish_the_linear_script(self):
        native = [node(0, "StartDialogueNode", Content="Choices", Outgoing=[1, 2]),
                  node(1, "PlayerChoiceDialogueNode", Content="First"),
                  node(2, "PlayerChoiceDialogueNode", Content="Second")]
        script = parse_dialogue_file(native, {})[0]["script"]
        self.assertEqual(script, [{"kind": "prompt", "options": [
            {"text": "First", "ends": False}, {"text": "Second", "ends": False}],
            "ends": True, "jump_to": None}])

    def test_long_graph_and_messages_have_no_collapse_or_recursion_cutoff(self):
        native = [node(0, "StartDialogueNode", Content="Long", Outgoing=[1])]
        for index in range(1, 1401):
            native.append(node(index, "DialogueNode", Content=f"Line {index}",
                               Outgoing=[index + 1]))
        native.append(node(1401, "EndDialogueNode", Outgoing=[0]))
        conversation = parse_dialogue_file(native, {}, "Amir")[0]
        self.assertEqual(len(conversation["graph"]["nodes"]), 1402)
        self.assertEqual(len(conversation["graph"]["edges"]), 1402)
        self.assertEqual(len(conversation["messages"]), 1400)
        self.assertEqual(len(conversation["script"]), 1400)
        self.assertTrue(conversation["script"][-1]["ends"])


class KimDMLoadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="kim-dm-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.data = self.root / "data"
        self.dicts = self.root / "dicts"
        self.data.mkdir()
        self.dicts.mkdir()

    def write_json(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def test_amir_loads_jabir_and_uses_en_localization_with_wiki_sender_fallback(self):
        native = [node(7, "StartDialogueNode", Content="AmirRank1Convo1", Outgoing=[9]),
                  node(9, "DialogueNode", LocTag="/hello", Outgoing=[12]),
                  node(12, "DialogueNode", Content="/hello", Speaker="/name",
                       Outgoing=[13]), node(13, "EndDialogueNode")]
        self.write_json(self.data / "JabirDialogue_rom.dialogue.json", native)
        self.write_json(self.dicts / "en.json", {"/hello": "English\nline",
                                                "/name": "English name"})
        self.write_json(self.dicts / "fr.json", {"/hello": "French line"})
        dm = KimDM(self.data, self.dicts)
        self.assertTrue(dm.available())
        self.assertEqual(dm.conversations_for("Amir"), [
            {"id": "AmirRank1Convo1", "title": "AmirRank1Convo1", "rank": "Rank 1",
             "source": "dm"}])
        conversation = dm.conversation("Amir", "AmirRank1Convo1")
        self.assertEqual(conversation["messages"], [
            {"index": 1, "speaker": "Amir", "text": "English\nline", "player": False,
             "lines": ["English", "line"]},
            {"index": 2, "speaker": "English name", "text": "English\nline", "player": False,
             "lines": ["English", "line"]}])
        self.assertEqual(dm.graph("Amir", "AmirRank1Convo1"), conversation["graph"])
        self.assertIsNone(dm.conversations_for("Jabir"))
        self.assertIsNone(dm.graph("Amir", "missing"))
        self.assertIsNone(dm.conversation("Missing", "Missing"))
        self.assertIsNone(dm.graph("Missing"))
        self.write_json(self.dicts / "en.json", {"/hello": "Reloaded", "/name": "Name"})
        dm.load()
        self.assertEqual(dm.conversation("Amir", "AmirRank1Convo1")["messages"][0]["text"],
                         "Reloaded")

    def test_aggregate_root_preserves_all_shared_and_parallel_routes(self):
        native = [
            node(10, "StartDialogueNode", Content="First", Outgoing=[10, 30]),
            node(20, "StartDialogueNode", Content="Second", Outgoing=[30]),
            node(30, "CheckCounterDialogueNode", CounterName="Score",
                 TrueNodes=[99], FalseNodes=[99], Outputs=[
                     {"Expression": "x > 1", "Outgoing": [99, 99]},
                     {"Expression": "false", "Outgoing": [99]}]),
            node(99, "EndDialogueNode"),
        ]
        self.write_json(self.data / "JabirDialogue_rom.dialogue.json", native)
        dm = KimDM(self.data, self.dicts)
        first = dm.graph("Amir", "First")
        second = dm.graph("Amir", "Second")
        aggregate = dm.graph("Amir")
        self.assertEqual(aggregate["rootId"], "root")
        self.assertEqual(aggregate["nodes"][0]["id"], "root")
        self.assertEqual({n["id"] for n in aggregate["nodes"]},
                         {"root", "dm10", "dm20", "dm30", "dm99"})
        roots = [e for e in aggregate["edges"] if e["source"] == "root"]
        self.assertEqual({e["target"] for e in roots}, {"dm10", "dm20"})
        native_edges = {e["id"]: e for e in first["edges"] + second["edges"]}
        self.assertEqual({e["id"]: e for e in aggregate["edges"] if e["source"] != "root"},
                         native_edges)
        self.assertEqual(len(aggregate["edges"]), len(native_edges) + 2)
        self.assertEqual(len(aggregate["edges"]), len({e["id"] for e in aggregate["edges"]}))
        self.assertEqual(len([e for e in aggregate["edges"] if e["source"] == "dm30"]), 5)
        self.assertEqual(first, dm.graph("Amir", "First"))

    def test_wiki_anchor_consumer_still_accepts_nodes_and_edges_without_native_fields(self):
        nodes = [{"id": "n_1", "speaker": "Amir", "text": "Hello", "player": False,
                  "terminal": False}, {"id": "n_2", "text": "Goodbye"}]
        edges = [{"source": "n_1", "target": "n_2", "label": ""}]
        graph = _anchor_graph(nodes, edges, "Wiki")
        self.assertEqual(graph["rootId"], "root")
        self.assertEqual(graph["nodes"][1:], nodes)
        self.assertEqual(graph["edges"][0], edges[0])
        self.assertEqual(graph["edges"][1]["target"], "n_1")
        self.assertEqual(_anchor_graph(nodes, edges, "Wiki", force=False)["nodes"], nodes)


if __name__ == "__main__":
    unittest.main()
