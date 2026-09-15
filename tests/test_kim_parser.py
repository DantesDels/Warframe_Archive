"""KIM dialogue extraction tests: parsing, junk exclusion, narration kept."""

from __future__ import annotations

import unittest

from warframe_lore.db.kim_parser import extract_kim_messages


def _speakers_and_texts(markdown: str) -> list[tuple[str, str, bool]]:
    return [(m.speaker, m.message_text, m.player_choice)
            for m in extract_kim_messages(markdown)]


class KimParserTests(unittest.TestCase):
    def test_bold_dialogue_lines_are_parsed_in_order(self):
        markdown = (
            "> **Amir:** Salut Tenno !\n"
            "> **Arthur:** On y va.\n")
        self.assertEqual(_speakers_and_texts(markdown), [
            ("Amir", "Salut Tenno !", False),
            ("Arthur", "On y va.", False),
        ])

    def test_branch_choices_are_player_input(self):
        markdown = (
            "> **Eleanor:** Choisis.\n"
            "> > La porte rouge\n"
            "> > La porte bleue\n")
        self.assertEqual(_speakers_and_texts(markdown), [
            ("Eleanor", "Choisis.", False),
            ("", "La porte rouge", True),
            ("", "La porte bleue", True),
        ])

    def test_plain_fallback_format(self):
        markdown = "> Amir : message sans gras\n"
        self.assertEqual(_speakers_and_texts(markdown),
                         [("Amir", "message sans gras", False)])

    def test_spoiler_artifacts_are_excluded(self):
        markdown = "> **__*_SPOILERS_*__ _:** cache\n"
        self.assertEqual(_speakers_and_texts(markdown), [])

    def test_sentence_like_speaker_is_excluded(self):
        markdown = (
            "> **Banishing an Eximus enemy will remove its Aura from enemies "
            "out of the Rift, eg:** if you Banish a Venomous Eximus\n")
        self.assertEqual(_speakers_and_texts(markdown), [])

    def test_junk_speakers_are_dropped(self):
        for speaker in ("Known Issue", "Reward", "NEW", "Complete Quest",
                        "Blueprint", "Boltor Model Updated",
                        "With 40.0.1, we fixed the Platinum issue"):
            markdown = f"> **{speaker}:** contenu technique\n"
            self.assertEqual(_speakers_and_texts(markdown), [],
                             msg=f"speaker {speaker!r} must be dropped")

    def test_numeric_only_messages_are_dropped(self):
        for value in ("40%", "1", "0.5%"):
            markdown = f"> **Amir:** {value}\n"
            self.assertEqual(_speakers_and_texts(markdown), [],
                             msg=f"value {value!r} must be dropped")

    def test_ui_label_messages_are_dropped(self):
        for message in ("Known Issue: this still happens",
                        "Reward: 1 Warframe Slot",
                        "NEW: Visit the Side Quest section of the Codex"):
            markdown = f"> **Arthur:** {message}\n"
            self.assertEqual(_speakers_and_texts(markdown), [],
                             msg=f"message {message!r} must be dropped")

    def test_narrative_uses_of_markers_are_kept(self):
        markdown = (
            "> **Arthur:** That's new.\n"
            "> **Roathe:** I think, for that, I shall reward you.\n"
            "> **Kaya:** I dug up some of her blueprint details.\n"
            "> **Flare:** I'm trying to fix this situation.\n"
            "> **Amir:** so talk to Arthur tomorrow and see if his "
            "username changed, it'll take about 24 hours for the system "
            "to update\n"
            "> **Flare:** standing on that stage, the new me, i felt alive\n")
        self.assertEqual(len(_speakers_and_texts(markdown)), 6)

    def test_real_kim_im_page_is_fully_kept(self):
        markdown = (
            "> **Quincy:** pssst. you still up?\n"
            "> > what's up?\n"
            "> **Quincy:** the boys are putting together a gig, "
            "wanna come?\n")
        self.assertEqual(_speakers_and_texts(markdown), [
            ("Quincy", "pssst. you still up?", False),
            ("", "what's up?", True),
            ("Quincy", "the boys are putting together a gig, "
             "wanna come?", False),
        ])


if __name__ == "__main__":
    unittest.main()
