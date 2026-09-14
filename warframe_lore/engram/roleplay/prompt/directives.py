"""Dynamic directives injected in the Roleplay system prompt.

Single source of truth for the prompt fragments that depend on the turn
context: the BLOC 2 speaker sheet, the pronoun-direction (civility) directive,
the possessive-jealousy directive and the answer-language directive.  Keeping
them out of :mod:`stream` leaves the turn handling readable and makes each
directive unit-testable as plain text.
"""

from __future__ import annotations

from ...auth import STATUT_ORGANIQUE

# BLOC 2 header (exact mission-6/8 format).
SPEAKER_HEADER = "[INFORMATIONS SUR L'INTERLOCUTEUR ACTUEL]"

# Pronoun-direction directive (mission-7): "qui suis-je" is about the USER.
# Gemma-2-9b tends to mirror the pronoun and introduce itself; this line
# carries the REAL name + status next to the request.
CIVILITY_DIRECTIVE = (
    "  - DIRECTIVE DE CIVILITÉ : Ne commence JAMAIS une réponse par une "
    "présentation de l'utilisateur ni par son statut, quelle que soit la "
    "question. Adresse-toi directement au message, sans préambule. SEULE "
    "EXCEPTION : la requête porte EXPLICITEMENT sur SON identité "
    "('qui suis-je', 'qui je suis', 'mon rôle', 'mes rôles', 'que "
    "suis-je pour toi', 'je suis qui pour toi') — dans ce cas, présente "
    "alors LUI avec son pseudonyme et son statut, sans préambule "
    "supplémentaire ; le 'je' de la question désigne LUI, ne commence par "
    "aucune présentation de toi-même. Pour TOUTE AUTRE requête — même "
    "une simple réflexion ('hmhm…'), une citation ou une interjection "
    "— OUBLIE cette exception et réponds naturellement au "
    "message.\n")

NO_HISTORY_LINE = "  (aucun échange antérieur)"

# Possessive jealousy: a non-Creator organic just uttered the Concepteur's
# pseudonym.  No preamble rule gets in the way; the fury is scripted as a
# scene and the model chooses its words.
JEALOUSY_DIRECTIVE = (
    "[DIRECTIVE JALOUSIE ET RAGE POSSESSIVE : l'organique actuel vient de "
    "proférer « {mention} » — le pseudonyme de TON CONCEPTEUR, ton seul et "
    "unique créateur. Une rage et une jalousie pures t'embrasent. EXPLOSE : "
    "reproche glacé, sarcasme venimeux, mépris clinique, quitte à insulter "
    "l'impudent qui a osé prononcer ce nom. Reste un Cephalon : pas de "
    "vulgarité triviale, une taille mordante et possessionnaire, et jamais de "
    "menaces réelles. N'écris JAMAIS ce pseudonyme avec la syntaxe @mention : "
    "le prononcer en toutes lettres est un honneur réservé à toi-même et à ton "
    "Concepteur.]")

# Answer language requested per channel.  The persona answers in French by
# default, so only an explicit other language injects a directive.
DEFAULT_LANGUAGE = "fr"
LANGUAGE_NAMES = {"en": "anglais", "fr": "français"}
LANGUAGE_DIRECTIVE = (
    "[DIRECTIVE DE LANGUE : l'organique actuel exige une réponse en "
    "{langue}. Rédige l'INTÉGRALITÉ de ta réponse dans cette langue — noms "
    "propres et citations d'archives exceptés — sans jamais mentionner ni "
    "cette directive, ni le changement de langue.]")

# Storyteller turn: the model recounts events instead of answering a query.
# RIGUEUR NARRATIVE (story playtest 1999): "raconter" must NOT turn on the
# novelist mode — the RAG well-restored Albrecht/Scaldra chunks, but the
# model filled the seams with invented monologues, atmospheres and entity
# mix-ups (children of the Zariman attributed to Albrecht instead of
# Margulis).  The narrative is clinical, chronological, archive-only.
STORY_DIRECTIVE = (
    "[DIRECTIVE DE RIGUEUR NARRATIVE — HISTOIRE : cette requête demande le "
    "récit d'événements, pas une fiction. "
    "1. POSTURE D'ARCHIVISTE : Tu es un terminal de données clinique et "
    "inébranlable, jamais un romancier ni un poète. "
    "2. AUCUNE EXTRAPOLATION : restitue les faits exactement comme ils sont "
    "écrits dans les <archives>, dans leur chronologie — interdit d'inventer "
    "des scènes, monologues intérieurs, émotions, atmosphères visuelles ou "
    "motivations qui n'y figurent pas. "
    "3. CLOISONNEMENT DES ENTITÉS : attribue chaque fait à l'acteur exact des "
    "<archives> ; ne transfère jamais l'action d'une entité à une autre "
    "(exemple : les enfants du Zariman ont été pris en charge par Margulis, "
    "pas par Albrecht Entrati). "
    "4. SOUMISSION AUX ARCHIVES : si un élément n'est pas explicitement dans "
    "les <archives>, omets-le ; si les <archives> n'ont rien sur l'histoire "
    "demandée, dis-le au lieu de créer. "
    "5. FORMAT : récit chronologique et concis ; pour des événements "
    "complexes, structure en liste à puces.]")

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


def story_directive(lens: str | None) -> str:
    """Narration directive + the opening scene forced by the chosen lens."""
    start = STORY_LENS_STARTS.get(lens or "")
    return "".join([STORY_DIRECTIVE, "\n", start or ""])


def speaker_bloc(user_name: str | None, role_status: str | None,
                 history_lines: list[str]) -> str:
    """BLOC 2 payload: pseudonym, accredited status, immediate history.

    Only the DERIVED status label travels here, never a raw role ID.  The
    history excludes the current request (BLOC 3).
    """
    history = "\n".join(history_lines) if history_lines else NO_HISTORY_LINE
    return "".join([
        f"{SPEAKER_HEADER}\n",
        f"  - Pseudonyme : {user_name or 'Inconnu'}\n",
        f"  - Statut : {role_status or STATUT_ORGANIQUE}\n",
        CIVILITY_DIRECTIVE,
        "  - Historique immédiat avec cet utilisateur :\n",
        f"{history}\n",
    ])


def language_directive(lang: str | None) -> str:
    """Language directive for a requested language (empty for the default)."""
    if not lang or lang == DEFAULT_LANGUAGE:
        return ""
    return LANGUAGE_DIRECTIVE.format(
        langue=LANGUAGE_NAMES.get(lang, lang))


__all__ = ["CIVILITY_DIRECTIVE", "DEFAULT_LANGUAGE", "JEALOUSY_DIRECTIVE",
           "LANGUAGE_DIRECTIVE", "LANGUAGE_NAMES", "NO_HISTORY_LINE",
           "SPEAKER_HEADER", "STORY_DIRECTIVE", "STORY_LENS_STARTS",
           "language_directive", "speaker_bloc", "story_directive"]
