"""Noise filtering and corpus-level frequency pruning for semantic entities."""

from __future__ import annotations

import re

from .models import Entity, Mention, Relation
from .patterns import NOISE_TOKEN_RE, STOP_ENTITIES

_LEADING_ARTICLE_RE = re.compile(
    r"^(?:the|a|an|le|la|les|un|une)[ \t]+(?=[A-ZÀ-ÖØ-Þ])",
    re.IGNORECASE,
)
_TRAILING_ROLE_RE = re.compile(r"[ \t]+roles?$", re.IGNORECASE)
_CONTRACTION_RE = re.compile(
    r"(?:\b(?:it|that|what|who|there|here|where|when|how|he|she|let|one)'s\b"
    r"|'(?:m|re|ve|ll|d|t)\b)",
    re.IGNORECASE,
)
_VERB_ADV_RE = re.compile(r"^[a-z]{4,}(?:ing|ed|ly)$", re.IGNORECASE)

NOISE_PREFIX_WORDS = frozenset({
    "your", "our", "my", "his", "her", "its", "their", "you", "we", "they",
    "he", "she", "it", "me", "him", "them", "us", "myself", "yourself",
    "himself", "herself", "themselves", "someone", "anyone", "everyone",
    "something", "anything", "everything", "nothing", "nobody",
    "upon", "when", "while", "where", "after", "before", "during", "since",
    "until", "although", "though", "despite", "instead", "because", "unless",
    "whether", "within", "without", "through", "throughout", "between",
    "among", "against", "towards", "toward", "around", "behind", "below",
    "above", "under", "over", "across", "along", "beyond", "inside", "outside",
    "added", "fixed", "removed", "changed", "updated", "increased", "decreased",
    "reduced", "improved", "adjusted", "replaced", "restored", "resolved",
    "disabled", "enabled", "corrected", "prevented", "allowed", "supported",
    "supporting", "using", "making", "taking", "giving", "getting", "having",
    "being", "doing", "going", "coming", "looking", "working", "playing",
    "continues", "continued", "continue", "ends", "ended", "starts", "started",
    "begins", "began", "fixes", "changes", "adds", "removes", "increases",
    "reduces", "allows", "prevents", "requires", "includes", "contains",
    "and", "but", "for", "nor", "yet", "so", "or", "as", "if", "of", "in",
    "on", "at", "to", "by", "up", "off", "out", "from", "into", "with",
    "then", "once", "here", "there", "why", "how", "all", "any", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "own", "same", "than", "too", "very", "can", "will", "just",
    "should", "would", "could", "may", "might", "must", "now", "well", "like",
    "back", "even", "still", "also", "already", "always", "never", "often",
    "sometimes", "perhaps", "maybe", "however", "therefore", "moreover",
    "furthermore", "additionally", "meanwhile", "otherwise", "similar",
    "different", "various", "several", "certain", "another", "every", "either",
    "neither", "enough", "much", "little", "less", "least", "first", "second",
    "third", "last", "next", "near", "hey", "hi", "hello", "yes", "yeah",
    "yep", "nope", "okay", "ok", "fine", "good", "great", "nice", "cool",
    "sure", "thanks", "thank", "please", "sorry", "wait", "stop", "look",
    "listen", "remember", "think", "know", "mean", "want", "need", "got",
    "get", "make", "made", "take", "took", "give", "gave", "come", "came",
    "go", "went", "gone", "see", "saw", "seen", "say", "said", "tell", "told",
    "ask", "asked", "try", "tried", "use", "used", "keep", "kept", "let",
    "put", "set", "run", "end",
})

NOISE_ANYWHERE_WORDS = frozenset({
    "scrollbox", "infobox", "navbox", "tooltip", "dropdown", "checkbox",
    "sidebar", "header", "footer", "modal", "dialog", "license", "success",
    "failure", "error", "warning", "notice", "click", "hover", "press",
    "toggle", "select", "default", "passive", "ability", "abilities",
    "damage", "survival", "stealth", "crowd", "health", "shield", "shields",
    "armor", "energy", "stamina", "affinity", "mastery", "rank", "level",
    "tier", "slot", "slots", "mod", "mods", "blueprint", "blueprints",
    "hotfix", "changelog", "transcript", "transcripts", "quote", "quotes",
    "convo", "conversation", "intro", "outro", "file", "files", "line",
    "lines", "client", "clients", "player", "players", "user", "users",
    "button", "patch", "version", "update", "updates", "role", "roles",
    "stat", "stats", "attribute", "attributes", "cooldown", "duration",
    "multiplier", "percentage", "bonus", "penalty", "mission", "missions",
    "sortie", "sorties", "alert", "alerts", "bounty", "bounties", "fissure",
    "fissures", "relic", "relics", "endo", "credits", "platinum", "ducats",
    "support", "jump", "resource", "resources", "chance", "drop", "drops",
    "standing", "inbox", "message", "messages", "ranks", "rifle", "pistol",
    "shotgun", "melee", "weapon", "weapons", "enemy", "enemies", "target",
    "targets", "container", "storage", "battery", "approach", "open", "closed",
    "friends", "friend", "hope", "anger", "fear", "joy", "sorrow", "envy",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday",
})


def clean_entity_surface(surface: str) -> str:
    """Normalize whitespace, punctuation and leading articles on a candidate."""
    clean = " ".join(surface.split()).strip(" -:,;()[]\"'!?./\\")
    clean = _LEADING_ARTICLE_RE.sub("", clean)
    clean = _TRAILING_ROLE_RE.sub("", clean)
    return clean.strip(" -:,;()[]\"'!?./\\")


def is_noisy_entity(clean: str, key: str, kind: str) -> bool:
    """Return True when a candidate surface is conversational, UI or patch noise."""
    if not key or len(key) < 3 or key in STOP_ENTITIES:
        return True
    if kind != "timeline" and NOISE_TOKEN_RE.match(clean):
        return True
    if _CONTRACTION_RE.search(clean):
        return True
    words = key.split()
    if not words or len(words) > 4:
        return True
    if any(len(w) <= 1 for w in words if not w.isdigit()):
        return True
    if words[0] in NOISE_PREFIX_WORDS or words[-1] in NOISE_PREFIX_WORDS:
        return True
    if any(w in STOP_ENTITIES or w in NOISE_ANYWHERE_WORDS for w in words):
        return True
    if len(words) == 1 and kind == "concept" and _VERB_ADV_RE.match(words[0]):
        return True
    return False


def prune_corpus_entities(
    entities: list[Entity],
    relations: list[Relation],
    mentions: list[Mention],
    doc_count: int,
) -> tuple[list[Entity], list[Relation], list[Mention]]:
    """Enforce minimum frequency and cap noisy concepts on multi-doc corpora."""
    if doc_count < 5:
        return entities, relations, mentions
    rel_endpoints = {r.source_id for r in relations} | {r.target_id for r in relations}
    kept: list[Entity] = []
    concepts: list[Entity] = []
    for ent in entities:
        if ent.kind == "concept":
            if ent.mention_count >= 3 and (
                len(ent.document_ids) >= 2 or ent.id in rel_endpoints
            ):
                concepts.append(ent)
        elif (
            ent.mention_count >= 2
            or len(ent.document_ids) >= 2
            or (ent.confidence >= 0.85 and ent.id in rel_endpoints)
        ):
            kept.append(ent)
    concepts.sort(
        key=lambda e: (-len(e.document_ids), -e.mention_count, e.name.casefold())
    )
    kept.extend(concepts[:350])
    kept.sort(key=lambda e: (-e.mention_count, -e.confidence, e.name.casefold()))
    kept_ids = {e.id for e in kept}
    clean_rels = [
        r for r in relations if r.source_id in kept_ids and r.target_id in kept_ids
    ]
    clean_mens = [m for m in mentions if m.entity_id in kept_ids]
    return kept, clean_rels, clean_mens
