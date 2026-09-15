"""Unit tests for the six structured parsers (no database required).

Each test uses a small Markdown fixture that mirrors the real wiki page
format, keeping the tests self-contained and fast.
"""

from __future__ import annotations

import textwrap

from warframe_lore.structured.catalog import parse_quest, parse_warframe_page
from warframe_lore.structured.dialogues import parse_dialogues
from warframe_lore.structured.fragments import parse_fragments
from warframe_lore.structured.news import parse_announcement, parse_update

# ---------------------------------------------------------------------------
# Dialogues
# ---------------------------------------------------------------------------


def _kim_md() -> str:
    return textwrap.dedent("""\
        > *_SPOILERS_* _: Spoiler_
        > All ending conversations will be marked as {Convo ends.}
        ## Conversation 1 (pop quiz)
        > **Amir:** hey future!!
        > **Amir:** anyway brb {Convo ends.}
        > > Sorry, brb [End]
        > **Amir:** har har we already have one
    """)


def _cinematic_md() -> str:
    return textwrap.dedent("""\
        ## Rescue the contractor
        > **Lotus:** Go to Stephano, Uranus.
        > **Lotus:** Good work, Tenno.
    """)


def test_kim_intro_skipped():
    lines = parse_dialogues("kim", "KIM · Amir", _kim_md())
    assert all(dlg.chapter != "_SPOILERS_" for dlg in lines)


def test_kim_chapter_tracked():
    lines = parse_dialogues("kim", "KIM · Amir", _kim_md())
    assert lines[0].chapter == "Conversation 1 (pop quiz)"


def test_kim_chemistry_gain():
    lines = parse_dialogues("kim", "KIM · Amir", _kim_md())
    gains = [dlg for dlg in lines if dlg.chemistry_gain]
    assert len(gains) == 1
    assert "brb" in gains[0].message_text.lower()
    assert "{Convo" not in gains[0].message_text


def test_kim_standalone_marker():
    md = "## C\n> **A:** foo\n> {Convo ends.}\n> **A:** bar\n"
    lines = parse_dialogues("kim", None, md)
    assert lines[0].chemistry_gain is True
    assert lines[1].chemistry_gain is False


def test_kim_chemistry_paren_and_bracket_variants():
    """Non-curly bracket markers [(…), […]] are also chemistry flags."""
    md = "## C\n> **A:** i'm done (Convo ends)\n> **A:** next line\n"
    lines = parse_dialogues("kim", None, md)
    assert lines[0].chemistry_gain is True
    assert "Convo ends" not in lines[0].message_text

    md2 = "## C\n> **A:** before\n> [Convo. End]\n> **A:** after\n"
    lines2 = parse_dialogues("kim", None, md2)
    assert lines2[0].chemistry_gain is True
    assert lines2[1].chemistry_gain is False


def test_kim_player_choice():
    lines = parse_dialogues("kim", None, _kim_md())
    choices = [dlg for dlg in lines if dlg.player_choice]
    assert len(choices) >= 1
    assert choices[0].speaker == ""


def test_cinematic_context_from_title():
    lines = parse_dialogues("cinematic", "Chains of Harrow", _cinematic_md())
    assert all(dlg.chapter == "Rescue the contractor" for dlg in lines)
    assert lines[0].speaker == "Lotus"


def test_plain_fallback():
    md = "## Intro\n> Lotus : I am watching.\n"
    lines = parse_dialogues("quote", "Test", md)
    assert lines[0].speaker == "Lotus"


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

_FRAG_MD = textwrap.dedent("""\
    **Glass Shard Fragments** are fragments of Lotos...

    Decrypting these fragments reveals lore narrated by **Onkko**.
    Glass Shard Fragments|glass
    fragment = Childhood Games
    |planet = Earth (Plains of Eidolon)
    |scans = 3
    |loretext = A picture of the young Ostron children playing together.
    This is the earliest known image of Saya.
    |narrator=Onkko
    |hiddentext = This is a secret entry.
    |audio=
    fragment = The Unyielding Kanzu
    |planet = Earth (Plains of Eidolon)
    |scans = 3
    |loretext = The waters once ran clear...
    |narrator=Onkko
    |hiddentext =
""")


def test_fragment_series_and_quest():
    series, quest, rows = parse_fragments(_FRAG_MD)
    assert series == "Glass Shard Fragments"
    assert quest is None


def test_fragment_multiline_loretext():
    _, _, rows = parse_fragments(_FRAG_MD)
    first = rows[0]
    assert "young Ostron" in first.item_text
    assert "Saya" in first.item_text


def test_fragment_secret_text():
    _, _, rows = parse_fragments(_FRAG_MD)
    assert rows[0].secret_text is not None


def test_fragment_empty_hiddentext():
    _, _, rows = parse_fragments(_FRAG_MD)
    assert rows[1].secret_text is None


def test_fragment_quest_context():
    md = textwrap.dedent("""\
        During the Saya's Vigil Quest you will find Glass Shards.
        Glass Shard Fragments|glass
        fragment = Test
        |planet = Earth
        |loretext = text
        |narrator = Ordis
    """)
    _, quest, rows = parse_fragments(md)
    assert quest == "Saya's Vigil"


# ---------------------------------------------------------------------------
# Warframes
# ---------------------------------------------------------------------------


def test_warframe_base_and_prime():
    md = textwrap.dedent("""\
        Warframe: Ash
        Ash
        Admirez le saint patron de l'ecole d'assassinat.
        Ash Prime
        La distraction et les subterfuges deviennent des armes mortelles.
        Rang
        0
        30
    """)
    rows = parse_warframe_page(md, "/fr/game/warframes/ash", "http://url")
    assert len(rows) == 2
    base, prime = rows
    assert (base.frame_name, base.is_prime) == ("Ash", False)
    assert (prime.frame_name, prime.is_prime) == ("Ash", True)
    assert "saint patron" in base.description.lower()
    assert "subterfuges" in prime.description.lower()


def test_warframe_no_prime():
    md = "Warframe: Citrine\nCitrine\nElle est belle.\nRang\n0\n30\n"
    rows = parse_warframe_page(md, "/fr/game/warframes/citrine", "u")
    assert len(rows) == 1
    assert rows[0].is_prime is False


def test_warframe_prime_page_only():
    md = (
        "Warframe: Ash Prime\n"
        "Ash\nBase blurb here.\n"
        "Ash Prime\nPrime blurb here.\n"
        "Rang\n0\n"
    )
    rows = parse_warframe_page(md, "/fr/game/warframes/ash-prime", "u")
    assert len(rows) == 1
    assert rows[0].is_prime is True
    assert "Prime blurb" in rows[0].description


# ---------------------------------------------------------------------------
# Quests
# ---------------------------------------------------------------------------


def test_quest_main_type():
    md = (
        '> "Story"\n'
        '> "Quest Description"\n'
        "**The New War** is a solo-only main Quest, released in 31.\n"
    )
    q = parse_quest(md, "The New War", "u")
    assert q is not None
    assert q.quest_name == "The New War"
    assert q.quest_type == "main"
    assert q.release_note == "31"


def test_quest_side_type():
    md = (
        "**A Man of Few Words** is a side Quest, "
        "released in Hotfix 17.4.3 (2015-09-16).\n"
    )
    q = parse_quest(md, "A Man of Few Words", "u")
    assert q.quest_type == "side"
    assert "Hotfix 17.4.3" in q.release_note


def test_quest_context():
    md = (
        '> "Darvo needs your help."\n'
        '> "Quest Description"\n'
        "**Test** is a main Quest, released in 10.\n"
    )
    q = parse_quest(md, "Test", "u")
    assert q.quest_context is not None
    assert "Darvo" in q.quest_context


def test_quest_subpage_skipped():
    q = parse_quest("text", "Erra/Transcript", "u")
    assert q is None


def test_quest_no_sentence_skipped():
    q = parse_quest("This is not a quest page.\n", "Proof Fragment", "u")
    assert q is None


# ---------------------------------------------------------------------------
# Patch notes
# ---------------------------------------------------------------------------


def test_update_old_format():
    md = textwrap.dedent("""\
        Warframe: Update 38.5: Techrot Encore
        Update
        ## Update 38.5: Techrot Encore
        pc
        Mar 19, 2025
        **UPDATE 38.5: TECHROT ENCORE**
        The floor shakes and the crowd cheers for more.
    """)
    u = parse_update(md, "/fr/patch-notes/pc/38-5-0", "u")
    assert u.version == "38.5.0"
    assert u.update_type == "Update"
    assert u.release_date == "Mar 19, 2025"
    assert "floor shakes" in u.summary


def test_update_new_format():
    md = textwrap.dedent("""\
        Warframe: MISE A JOUR 39 : LA TOILE INSULAIRE
        Mise a jour principale
        ## MISE A JOUR 39
        pc
        Jun 25, 2025
        # **MISE A JOUR 39 : LA TOILE INSULAIRE**
        ### **Retournez a Duviri**
        Retournez au Royaume flottant de Duviri.
    """)
    u = parse_update(md, "/fr/patch-notes/pc/39-0-0", "u")
    assert u.update_type == "Mise a jour principale"
    assert "Duviri" in u.summary


# ---------------------------------------------------------------------------
# Announcements
# ---------------------------------------------------------------------------


def test_announcement_standard():
    md = textwrap.dedent("""\
        Warframe: Resume du Devstream 197
        Resume du Devstream 197
        Plongez au coeur de La Lame de Givre de Narin !
        Publié sur 2026-09-08 16:03:00
        Tweet
        Diffuse en direct devant le public de TennoCon 2026.
    """)
    a = parse_announcement(md, "/fr/news/resume-du-devstream-197", "u")
    assert a.title == "Resume du Devstream 197"
    assert a.published_at == "2026-09-08 16:03:00"
    assert "TennoCon" in a.summary


def test_announcement_landing_page():
    md = textwrap.dedent("""\
        Warframe: Prime Resurgence
        - Current Primes
        -
        - Earn In-Game Access
        Prime Resurgence
        Banshee Prime & Mirage Prime
        Now you can upgrade your Arsenal with Prime Resurgence.
    """)
    a = parse_announcement(md, "/fr/news/banshee-prime-resurgence", "u")
    assert a.title == "Prime Resurgence"
    assert a.subtitle == "Banshee Prime & Mirage Prime"
