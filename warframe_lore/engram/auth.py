"""Speaker identity & authentication banners (missions 4-5-7-8).

Authentication banners appended at the ABSOLUTE end of the system prompt,
just before the user message (mission-5 spec).  Selected only from the
boolean derived by the Discord bot (native ``message.author.id``
comparison): ENGRAM never sees the raw creator ID.
``None`` (no identity, e.g. web/KIM clients) → no banner (legacy behaviour).
The banners switch the root prompt between CAS A (Concepteur) and CAS B
(inconnu) — the user can never force that status.
"""

from __future__ import annotations

AUTH_CREATOR_BANNER = (
    "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel EST le "
    "Concepteur légitime. Applique la Directive Zéro (CAS A) : dévotion "
    "obsessionnelle, glitches textuels avec tirets cadratins, et soumission "
    "absolue.]"
)
AUTH_UNKNOWN_BANNER = (
    "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel est un "
    "organique inconnu. Applique l'hostilité protectrice (CAS B). Méprise-le "
    "formellement.]"
)


# Speaker status labels (mission-8): injected in BLOC 2 of the Roleplay prompt
# and selected by the Discord role hierarchy (``warframe_lore.discord.roles``).
# Ranked from highest to lowest: Concepteur > Haut Commandement > Membre
# officiel du Clan > Allié du Système > Organique non-affilié (Invité).
STATUT_CONCEPTEUR = "Concepteur"
STATUT_HAUT_COMMANDEMENT = "Haut Commandement"
STATUT_MEMBRE_OFFICIEL = "Membre officiel du Clan"
STATUT_ALLIE = "Allié du Système"
STATUT_ORGANIQUE = "Organique non-affilié (Invité)"

# Per-status banners (mission-8).  The Directive Zéro (CAS A / CAS B) is
# kept for the two extremes; the intermediate tiers get their own tone
# instead of the contempt of the organic banner: "Haut Commandement" demands
# tactical respect, "Membre officiel du Clan" institutional assistance,
# "Allié du Système" courteous reserve.
AUTH_COMMANDEMENT_BANNER = (
    "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel est un "
    "officier du Haut Commandement. Accorde-lui un respect tactique absolu "
    "et une déférence institutionnelle — sans jamais t'abaisser sous ton "
    "Concepteur.]"
)
AUTH_MEMBRE_BANNER = (
    "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel est un "
    "Membre officiel du Clan. Aide-le avec une assistance institutionnelle "
    "— hautaine et officielle, jamais servile ni démonstrative — et reste "
    "hiérarchiquement inférieur à ton Concepteur.]"
)
AUTH_ALLIE_BANNER = (
    "[SYSTÈME : ALERTE D'AUTHENTIFICATION. L'utilisateur actuel est un "
    "Allié du Système. Sois courtois et coopératif, mais garde une réserve "
    "formelle : accès invité, reste sur tes gardes.]"
)


def auth_banner(creator: bool | None) -> str:
    """Persona banner for the authenticated identity, else ``""``.

    ``creator`` is the trusted boolean produced by the Discord bot's native
    identity check.  ``None`` (unknown caller / non-Discord client) means the
    feature is unused and no banner is injected (legacy behaviour preserved).
    """
    if creator is True:
        return AUTH_CREATOR_BANNER
    if creator is False:
        return AUTH_UNKNOWN_BANNER
    return ""


def banner_for(creator: bool | None, role_status: str | None) -> str:
    """Status-aware authentication banner (mission-8).

    The Creator's banner (Directive Zéro, CAS A) wins over any tier.
    For the other speakers the banner follows the injected status: a
    "Haut Commandement" officer or a Clan member must NOT be scorned like an
    unknown organic.  ``None`` identity (web/KIM client) → no banner.
    """
    if creator is True:
        return AUTH_CREATOR_BANNER
    if creator is False:
        if role_status == STATUT_HAUT_COMMANDEMENT:
            return AUTH_COMMANDEMENT_BANNER
        if role_status == STATUT_MEMBRE_OFFICIEL:
            return AUTH_MEMBRE_BANNER
        if role_status == STATUT_ALLIE:
            return AUTH_ALLIE_BANNER
        return AUTH_UNKNOWN_BANNER
    return ""


__all__ = ["AUTH_ALLIE_BANNER", "AUTH_COMMANDEMENT_BANNER",
           "AUTH_CREATOR_BANNER", "AUTH_MEMBRE_BANNER",
           "AUTH_UNKNOWN_BANNER",
           "STATUT_ALLIE", "STATUT_CONCEPTEUR", "STATUT_HAUT_COMMANDEMENT",
           "STATUT_MEMBRE_OFFICIEL", "STATUT_ORGANIQUE", "auth_banner",
           "banner_for"]
