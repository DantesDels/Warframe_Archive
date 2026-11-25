"""Declarative FR/EN patterns for multi-universe entity & relation extraction."""

from __future__ import annotations

import re

PROPER_NOUN_RE = re.compile(
    r"\b([A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ0-9'-]{2,}(?:[ \t]+(?:of|the|de|du|des|la|le|d'|l')?"
    r"[ \t]*[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ0-9'-]{1,}){0,3})\b"
)
TIMELINE_RE = re.compile(
    r"\b("
    r"(?:Era|Age|Epoch|Cycle|Millennium|Century|Year|Ère|Âge|Époque|Guerre|Siècle)"
    r"[ \t]+(?:of[ \t]+(?:the[ \t]+)?|de[ \t]+(?:la[ \t]+|l')?|du[ \t]+|des[ \t]+)?"
    r"[A-ZÀ-ÖØ-Þ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'-]{1,28}"
    r"|(?:Old|New|Great|First|Second|Third)[ \t]+War"
    r"|An[ \t]+\d{1,4}"
    r"|\d{1,4}[ \t]*(?:BBY|ABY|BC|AD|BCE|CE|av\.[ \t]*J\.-C\.|ap\.[ \t]*J\.-C\.)"
    r"|(?:19[0-9]{2}|20[0-2][0-9])"
    r")\b"
)
ALIAS_RE = re.compile(
    r"([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36}?)\s*"
    r"(?:\((?:a\.?k\.?a\.?|alias|also known as|connu sous le nom de|surnommé|dit)\s+"
    r"([^)]{2,40})\)|"
    r"(?:,?\s*(?:also known as|a\.?k\.?a\.?|connu sous le nom de|surnommé)\s+"
    r"[\"«']?([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ0-9' -]{2,36})[\"»']?))",
    re.IGNORECASE,
)
NOISE_TOKEN_RE = re.compile(r"^(?:[PQ]\d{3,}|https?|www\b|\d{1,3})$", re.IGNORECASE)

STOP_ENTITIES = frozenset({
    "the", "this", "that", "these", "those", "there", "their", "they", "when",
    "where", "while", "after", "before", "during", "under", "about", "other",
    "how", "what", "which", "who", "from", "into", "some", "many", "more",
    "most", "all", "any", "each", "also", "here", "such", "only", "new",
    "les", "des", "une", "dans", "pour", "avec", "sans", "mais", "donc", "puis",
    "comme", "cette", "cet", "ceux", "celui", "celle", "ils", "elles", "vous",
    "nous", "elle", "entre", "selon", "après", "avant", "pendant", "tous",
    "tout", "plus", "voir", "aussi", "comment", "pourquoi", "quand", "toutes",
    "toute", "ces", "pack", "packs", "mise", "size",
    "note", "notes", "main", "page", "home", "wiki", "edit", "history",
    "references", "trivia", "gallery", "summary", "overview", "introduction",
    "contents", "external", "categories", "category", "catégorie", "sommaire",
    "références", "galerie", "histoire", "présentation", "description", "patch",
    "update", "updates", "jeu", "acheter", "utiliser", "afficher", "cliquer",
    "connexion", "inscription", "recherche", "menu", "role", "roles", "buy",
    "shop", "store", "login", "signup", "download", "play", "free", "privacy",
    "terms", "cookies", "copyright", "english", "français", "francais",
    "deutsch", "español", "espanol", "italiano", "português", "portugues",
    "polski", "türkçe", "turkce", "русский", "日本語", "한국어", "中文",
})

KIND_CLUES: dict[str, tuple[str, ...]] = {
    "location": (
        "planet", "planète", "city", "ville", "citadel", "citadelle", "world",
        "monde", "system", "système", "station", "sector", "secteur", "region",
        "région", "fortress", "forteresse", "temple", "moon", "lune", "island",
        "île", "kingdom", "royaume", "capital", "capitale", "desert", "désert",
        "located in", "situé", "située", "surface of", "orbit",
    ),
    "faction": (
        "faction", "empire", "republic", "république", "syndicate", "syndicat",
        "order", "ordre", "clan", "guild", "guilde", "house", "maison", "legion",
        "légion", "alliance", "council", "conseil", "corps", "cult", "culte",
        "brotherhood", "confrérie", "organization", "organisation", "army", "armée",
    ),
    "person": (
        "character", "personnage", "leader", "chef", "founder", "fondateur",
        "scientist", "scientifique", "doctor", "docteur", "emperor", "empereur",
        "king", "roi", "queen", "reine", "captain", "capitaine", "warrior",
        "guerrier", "hero", "héros", "master", "maître", "member", "membre",
        "born", "né", "née", "son of", "daughter of", "fils de", "fille de",
    ),
}

RELATION_TRIGGERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("BELONGS_TO", (
        "member of", "belongs to", "part of the faction", "serves the",
        "membre de", "appartient à", "sert le", "sert la", "issu de",
    )),
    ("LOCATED_IN", (
        "located in", "located on", "situated in", "found in", "based on",
        "situé sur", "située sur", "situé dans", "située dans", "trouvé sur",
        "basé sur", "originaire de",
    )),
    ("CREATED_BY", (
        "created by", "built by", "forged by", "founded by", "designed by",
        "créé par", "créée par", "construit par", "forgé par", "fondé par",
    )),
    ("OPPOSES", (
        "enemy of", "opposes", "fights against", "war against", "rival of",
        "ennemi de", "opposé à", "combat", "guerre contre", "rival de",
    )),
    ("ALLIED_WITH", (
        "allied with", "ally of", "allies with", "partner of",
        "allié de", "alliée de", "allié avec", "partenaire de",
    )),
    ("PART_OF", (
        "part of", "subdivision of", "branch of", "component of",
        "partie de", "branche de", "composant de",
    )),
    ("OCCURRED_IN", (
        "occurred in", "happened during", "took place in", "during the",
        "eut lieu", "pendant", "durant", "au cours de",
    )),
)
