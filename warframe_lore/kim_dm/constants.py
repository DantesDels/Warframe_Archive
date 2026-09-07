"""Constantes de la datamine KIM (source GitHub + fichiers + moteur)."""

from __future__ import annotations

REPO = "Sainan/warframe-kim-dialogues"
BRANCH = "senpai"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"

# Fichiers de dialogue du jeu par personnage (dossier ``data/`` du miroir).
# Les stubs ``MinervaDialogue``/``VelimirDialogue`` (782 o) redirigent vers la
# conversation combinée ``MinVel*`` : on les télécharge (miroir complet) mais
# ils n'exposent aucune donnée propre.
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

# Page wiki (dernier segment du titre « Kinemantik Instant Messenger/X ») ->
# fichier de datamine correspondant.  Les personnages absents de ce mapping
# (Fables & Frontiers, stubs Minerva/Velimir) retombent sur l'analyse
# des sections wiki (fallback historique).
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

# Seuls les types natifs exacts déterminent le rôle d'un nœud.
_ENGINE = "/EE/Types/Engine/"
_NODE_KINDS = {
    _ENGINE + "StartDialogueNode": "start",
    _ENGINE + "DialogueNode": "npc",
    _ENGINE + "PlayerChoiceDialogueNode": "choice",
    _ENGINE + "ChemistryDialogueNode": "chemistry",
    _ENGINE + "EndDialogueNode": "end",
}

_USER_AGENT = "WarframeLoreScraper/1.0 (kim datamine mirror; local tool)"