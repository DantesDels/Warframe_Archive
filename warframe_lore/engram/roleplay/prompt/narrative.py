"""Narrative directives: how a storyteller turn stays on the archives.

Single source of truth for the fragments that shape a STORY turn: the semantic
quarantine (brute prose, pretrained amnesia, strict stop, French-only), the
English-archive primacy, the targeted era lock, the Leverian source lock, the
resume rule of a continuation and the mandatory closing line of a part.

A narrative is served in PARTS (``protocols.STORY_DOSSIER_PAGE`` chunks each):
the closing line therefore depends on the pagination state — an invitation to
ask for more while fragments remain, an archivist closing once the dossier is
exhausted.  Keeping the two sentences here (and nowhere else) is what makes
that switch a single-source decision.
"""

from __future__ import annotations

# Mandatory last line of a narrative part.  Two states, one slot: the
# invitation while the subject's dossier still holds unseen fragments, the
# closing once it does not.
STORY_PAGINATION_SENTENCE = (
    "Le Tissage de données contient d'autres fragments à ce sujet. Ordonnez-moi "
    "de poursuivre pour les déverrouiller, organique.")
STORY_COMPLETE_SENTENCE = (
    "Le Tissage de données n'a plus de fragments inédits sur ce sujet ; le "
    "récit s'achève là, organique.")

# Storyteller turn: the persona's "ARCHIVE DU CODEX" forces a filled tactical
# sheet and the archives of a narrative-only entity leave blanks — the model
# then either steals another character's lore (Albrecht/Perintol playtest) or,
# freed from the Codex, drains its PRETRAINED weights once the <archives> run
# out (Albrecht/Trivia playtest: Adalbert/Bengel etymology, English leak).  The
# narrative turn therefore applies an ABSOLUTE SEMANTIC QUARANTINE: brute
# narrative formatting, pretrained amnesia, a hard content lock with strict
# stop, a French-only lock, and one fixed closing sentence.
_STORY_BASE = (
    "[DIRECTIVE DE QUARANTAINE SÉMANTIQUE ABSOLUE — REQUÊTE NARRATIVE : la "
    "règle « MISE EN PAGE DU LORE (ARCHIVE DU CODEX) » du système est "
    "DÉSACTIVÉE pour cette requête. "
    "1. FORMATAGE NARRATIF BRUT : une requête « Raconte-moi… », « Quelle est "
    "l'histoire… » est narrative : DÉSACTIVE le format Codex — aucun en-tête, "
    "aucune liste à puces, aucune section « Spécifications ». Rédige "
    "uniquement des paragraphes de texte suivis. "
    "2. AMNÉSIE PRÉ-ENTRAÎNÉE (ZÉRO TRIVIA) : tu es frappé d'amnésie totale "
    "sur le Système Origine en dehors de ce qui est écrit mot pour mot dans la "
    "balise <archives>. Interdiction stricte d'ajouter des anecdotes de "
    "développement, des étymologies du monde réel (« origine allemande », "
    "« traduction italienne », « mythologie terrestre ») ou des faits absents "
    "du contexte fourni. "
    "3. VERROU DE CONTENU ET ARRÊT STRICT : ton seul travail est de "
    "paraphraser avec une prose d'archiviste solennelle les faits EXACTS de "
    "la balise <archives>, sans aucune déduction. Dès que tu as couvert tous "
    "les faits du texte fourni, ARRÊTE ta génération — n'allonge jamais "
    "l'histoire pour combler un vide. "
    "4. VERROU LINGUISTIQUE : la génération reste intégralement en français ; "
    "toute bascule en anglais est formellement interdite. ")
_STORY_PAGINATION_ITEM = (
    "5. PAGINATION DIÉGÉTIQUE : clôture impérativement toute réponse narrative "
    "par cette phrase exacte et rien d'autre : « {} »]")
STORY_DIRECTIVE = _STORY_BASE + _STORY_PAGINATION_ITEM.format(
    STORY_PAGINATION_SENTENCE)

# The three canonical starting points of a story.  Keys match the lens ids
# agreed client-side (``protocols.roleplay``): never duplicated literals here.
STORY_LENS_STARTS = {
    "initiate": ("Commence par l'éveil des Tenno : les enfants revenus du "
                 "Zariman, pris en charge par Margulis dans les rêves"),
    "cosmogonic": ("Commence par la découverte du Vide par Albrecht Entrati "
                   "et l'arrivée de l'Indifférence."),
    "1999": ("Commence en l'an 1999 dans la cité-état de Höllvania, front "
             "urbain ravagé par le Technocyte et quadrillé par la milice du "
             "Scaldra, sur la piste de l'expérience d'Albrecht Entrati."),
}

# Bilingual archives primacy: the dossier may hold the same entity in the
# English source AND in its French translation.  English is the primary
# source (ingested first, tier-0 of the dossier); French is a reading aid
# that must never contradict it.  Complements the dossier ordering.
EN_PRIMACY_DIRECTIVE = (
    "[DIRECTIVE DE PRIMAUTÉ DES ARCHIVES ANGLAISES : le dossier peut contenir "
    "la même entité dans sa version anglaise d'origine ET dans sa traduction "
    "française. La version ANGLAISE fait foi : c'est la source primaire. En "
    "cas d'écart entre les deux, fonde ton récit sur la version anglaise — la "
    "française n'est qu'une aide de lecture et ne doit jamais la contredire "
    "ni la compléter de ton propre chef.]")

# Targeted narrative request: the user named a specific subject.  The answer
# must be anchored in that subject's own era and must NEVER bridge to another
# temporal starting point (e.g. Eleanor/1999 must not drift to Zariman/Margulis).
TARGETED_STORY_DIRECTIVE = (
    "[DIRECTIVE DE VERROU SPATIO-TEMPOREL — REQUÊTE CIBLÉE : l'organique a "
    "nommé un sujet précis. 1. ANCRAGE DANS LA BONNE ÈRE : le récit reste "
    "intégralement dans la temporalité propre de ce sujet (Ère Orokin, An 1999, "
    "Vieille Guerre, etc.), telle que dictée par les archives fournies. "
    "2. INTERDICTION DE PONT TEMPOREL : il est formellement interdit de relier "
    "ce sujet à un autre point de départ temporel pour 'faire le lien'. Si le "
    "sujet appartient à 1999, le récit commence et reste en 1999 : aucune "
    "mention du Zariman, de Margulis ou de l'Éveil. 3. ARRÊT STRICT : une fois "
    "les faits du contexte épuisés, stoppe — n'invente jamais des connexions "
    "inter-ères absentes des archives.]")

# Leverian Warframe: Drusus Leverian is the canonical narrator for these
# frames.  The model must ground the tale on his Leverian gallery and treat
# his narration as the primary source.
LEVERIAN_DIRECTIVE = (
    "[DIRECTIVE SOURCES DU LEVERIAN — Ce Warframe possède une galerie Leverian "
    "narrée par Drusus Leverian. Tu DOIS te baser sur les dires de Drusus et "
    "les artefacts du Leverian pour raconter cette histoire. Privilégie les "
    "passages du contexte où Drusus est le narrateur. Ne mélange pas cette "
    "version avec des récits tiers ou des spéculations communautaires.]")

# Continuation of a RUNNING narrative: the history already holds the previous
# parts.  Without this rule the model re-opens the tale and re-narrates the
# very same passages (observed playtest: an identical "continue" answer).
STORY_RESUME_DIRECTIVE = (
    "[DIRECTIVE DE REPRISE DU RÉCIT (l'histoire est DÉJÀ commencée — voir "
    "l'historique) : n'ouvre pas le récit, ne le résume pas et ne répète pas "
    "ce qui a déjà été raconté. ZÉRO RÉPÉTITION : interdiction absolue de "
    "reprendre une phrase, un fait ou une scène déjà écrits dans une partie "
    "précédente — raconte exclusivement la SUITE. Enchaîne directement sur de "
    "NOUVEAUX faits des <archives> fournies, comme le paragraphe suivant de "
    "la même histoire.]")

# Closing line of a part: the invitation while fragments remain, the archivist
# closing once the dossier is exhausted (the tale is over — asking for "more"
# would only make the model repeat itself).
_STORY_PAGINATION_DIRECTIVE = (
    "[DIRECTIVE DE PAGINATION DIÉGÉTIQUE : clôture impérativement le récit par "
    "cette phrase exacte et rien d'autre : « {} »]")
_STORY_EXHAUSTED_DIRECTIVE = (
    "[DIRECTIVE DE CLÔTURE DES ARCHIVES : la pagination diégétique est "
    "DÉSACTIVÉE — le Tissage de données n'a plus de fragments inédits sur ce "
    "sujet. Clôture impérativement le récit par cette phrase exacte et rien "
    "d'autre : « {} »]")


def story_closing(more: bool) -> str:
    """Mandatory last line of a narrative part (``more``: an invitation)."""
    if more:
        return _STORY_PAGINATION_DIRECTIVE.format(STORY_PAGINATION_SENTENCE)
    return _STORY_EXHAUSTED_DIRECTIVE.format(STORY_COMPLETE_SENTENCE)


def resume_directive(continuation: bool) -> str:
    """Resume fragment of a part that continues a running narrative (``""``)."""
    return f"\n{STORY_RESUME_DIRECTIVE}" if continuation else ""


def leverian_directive(frame: str) -> str:
    """Directive anchoring a Warframe story to Drusus' Leverian gallery."""
    return f"{LEVERIAN_DIRECTIVE}\n  - Warframe Leverian ciblé : {frame}."


def story_directive(lens: str | None, *, continuation: bool = False,
                    more: bool = True) -> str:
    """Narration directive + the opening scene forced by the chosen lens.

    A continuation drops the opening scene (the tale runs: it resumes).  An
    exhausted dossier supersedes the pagination rule with the closing line.
    """
    start = None if continuation else STORY_LENS_STARTS.get(lens or "")
    extra = resume_directive(continuation)
    if not more:
        extra += f"\n{story_closing(more=False)}"
    return "".join([STORY_DIRECTIVE, extra, "\n", EN_PRIMACY_DIRECTIVE, "\n",
                    start or ""])


def targeted_story_directive(era: str | None = None, *,
                             continuation: bool = False,
                             more: bool = True) -> str:
    """Era-anchored directive for a targeted narrative request.

    The targeted block carries no closing rule of its own: the mandatory last
    line (invitation or archivist closing) is appended here for both states.
    """
    era_line = f"\n  - Ère imposée par les archives : {era}." if era else ""
    return "".join([TARGETED_STORY_DIRECTIVE, resume_directive(continuation),
                    "\n", EN_PRIMACY_DIRECTIVE, era_line, "\n",
                    story_closing(more)])


__all__ = ["EN_PRIMACY_DIRECTIVE", "LEVERIAN_DIRECTIVE",
           "STORY_COMPLETE_SENTENCE", "STORY_DIRECTIVE", "STORY_LENS_STARTS",
           "STORY_PAGINATION_SENTENCE", "STORY_RESUME_DIRECTIVE",
           "TARGETED_STORY_DIRECTIVE", "leverian_directive",
           "resume_directive", "story_closing", "story_directive",
           "targeted_story_directive"]
