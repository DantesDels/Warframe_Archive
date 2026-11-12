"""Constants for the KIM datamine (GitHub source + files + engine)."""

from __future__ import annotations

REPO = "Sainan/warframe-kim-dialogues"
BRANCH = "senpai"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"

# Per-character game dialogue files (``data/`` folder of the mirror).
# The ``MinervaDialogue``/``VelimirDialogue`` stubs (782 B) redirect to the
# combined ``MinVel*`` conversation: they are downloaded (full mirror) but
# expose no own data.
DIALOGUE_FILES = (
    "AoiDialogue_rom.dialogue.json",
    "ArthurDialogue_rom.dialogue.json",
    "EleanorDialogue_rom.dialogue.json",
    "FlareDialogue_rom.dialogue.json",
    "HexDialogue_rom.dialogue.json",
    "JabirDialogue_rom.dialogue.json",
    "KayaDialogue_rom.dialogue.json",
    "LettieDialogue_rom.dialogue.json",
    "LoidDialogue_rom.dialogue.json",
    "LyonDialogue_rom.dialogue.json",
    "MarieDialogue_rom.dialogue.json",
    "MinervaDialogue_rom.dialogue.json",
    "MinervaVelemirDialogue_rom.dialogue.json",
    "QuincyDialogue_rom.dialogue.json",
    "RoatheDialogue_rom.dialogue.json",
    "VelimirDialogue_rom.dialogue.json",
)

DIALECT_FILE_PREFIX = "Dialogue_rom.dialogue.json"

# Wiki page (last segment of the « Kinemantik Instant Messenger/X » title) ->
# matching datamine file.  Characters missing from this mapping (Fables &
# Frontiers, Minerva/Velimir stubs) fall back to wiki section analysis
# (legacy fallback).
WIKI_PAGE_MAP = {
    "Amir": "Jabir",
    "Arthur": "Arthur",
    "Aoi": "Aoi",
    "Eleanor": "Eleanor",
    "Flare": "Flare",
    "Kaya": "Kaya",
    "Leticia": "Lettie",
    "Loid": "Loid",
    "Lyon": "Lyon",
    "Marie": "Marie",
    "Quincy": "Quincy",
    "Roathe": "Roathe",
    "Minerva, Velimir": "MinervaVelemir",
}

DATA_DIRNAME = "data"
DICTS_DIRNAME = "dicts"
SUPPORTED_LANGS = ("de", "en", "es", "fr", "it", "ja", "ko", "pl", "pt",
                   "ru", "tc", "th", "tr", "uk", "zh")

# Only exact native types determine a node's role.
_ENGINE = "/EE/Types/Engine/"
_NODE_KINDS = {
    _ENGINE + "StartDialogueNode": "start",
    _ENGINE + "DialogueNode": "npc",
    _ENGINE + "PlayerChoiceDialogueNode": "choice",
    _ENGINE + "ChemistryDialogueNode": "chemistry",
    _ENGINE + "EndDialogueNode": "end",
}

_USER_AGENT = "WarframeLoreScraper/1.0 (kim datamine mirror; local tool)"
