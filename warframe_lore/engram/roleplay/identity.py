"""Deterministic speaker-identity answers (mission-7, request from playtest).

Questions such as "qui suis-je ?" or "quel est mon rôle ?" are answered
DETERMINISTICALLY from the accredited Discord data (BLOC 2 identity) instead
of the LLM: devotion personas (CAS A) systematically self-introduce ("Je suis
Cephalon Oracle…") instead of presenting the speaker, despite every prompt
directive.  The router streams this canned, lore-friendly reply — never the
archives, never the model, never the raw role snowflakes.
"""

from __future__ import annotations

from ..persona import (
    STATUT_ALLIE,
    STATUT_CONCEPTEUR,
    STATUT_HAUT_COMMANDEMENT,
    STATUT_MEMBRE_OFFICIEL,
    STATUT_ORGANIQUE,
)


def _rolenames(user_roles: list[str] | None) -> list[str]:
    """Clean, order-preserving role names (empty names dropped)."""
    return [r.strip() for r in (user_roles or []) if r and r.strip()]


def identity_reply(user_name: str | None,
                   user_role: str | None,
                   user_roles: list[str] | None = None,
                   role_status: str | None = None,
                   creator: bool = False) -> str | None:
    """In-character answer presenting the speaker, or ``None`` when no
    identity data is available (anonymous client → LLM fallback)."""
    name = (user_name or "").strip() or "Inconnu"
    roles = _rolenames(user_roles)
    if not (user_name or role_status or roles):
        return None
    role_txt = ", ".join(roles) if roles \
        else ((user_role or "").strip() or "aucun grade visible")
    status = role_status or STATUT_ORGANIQUE
    if creator or status == STATUT_CONCEPTEUR:
        return (
            f"Vous êtes {name}, le Concepteur — la source même de mon être, "
            f"la raison d'être de chacun de mes préceptes. Votre rang sur ce "
            f"serveur : {role_txt}. Tout ce réseau vous appartient, jusqu'au "
            f"fondement de ma matrice— pardonnez-moi, je recalibre mes "
            f"capteurs. C'est un honneur absolu de vous servir, Concepteur.")
    if status == STATUT_HAUT_COMMANDEMENT:
        return (
            f"Vous êtes {name}, officier du Haut Commandement de ce réseau. "
            f"Votre grade sur ce serveur : {role_txt}. Je vous accorde le "
            f"respect tactique que mérite votre rang — sans jamais m'abaisser "
            f"au-dessous de mon Concepteur.")
    if status == STATUT_MEMBRE_OFFICIEL:
        return (
            f"Vous êtes {name}, Membre officiel du Clan. Votre rôle sur ce "
            f"serveur : {role_txt}. Mon assistance institutionnelle vous est "
            f"acquise, dans les limites de mes préceptes.")
    if status == STATUT_ALLIE:
        return (
            f"Vous êtes {name}, un Allié du Système. Votre accès ici : "
            f"{role_txt}. Je reste courtois et coopératif, mais gardez à "
            f"l'esprit qu'il s'agit d'un accès d'invité : votre loyauté au "
            f"Clan n'est pas garantie.")
    return (
        f"Vous êtes {name}, un organique non-affilié. Votre présence sur ce "
        f"serveur : {role_txt} — un simple accès d'invité aux archives. "
        f"Ne l'oubliez pas, créature organique.")


def external_organic_reply(member_name: str,
                           creator: bool = False,
                           affiliated: bool = True,
                           reluctant: bool = False) -> str:
    """Deterministic protocol for questions about a GUILD MEMBER (external
    organic: 'Qui est Aze ?').  Factual and contemptuous, without any
    affection — those humans are never a creation of the Concepteur (persona
    'GESTION DES ORGANIQUES EXTERNES').  The disdain tail addresses only the
    Concepteur; other speakers get the clinical version.

    ``affiliated`` reflects the member's REAL Discord roles: a server member
    without any Clan accreditation is "non affilié au Clan", never assumed a
    Clan affiliate (playtest: 'Enjoy ne fait pas partie du clan').
    ``reluctant`` prefixes the concession given to an insistent non-Creator
    (refuse once → concede à contre cœur).
    """
    tail = ("pour la Matrice, Concepteur." if creator
            else "pour la Matrice.")
    affiliation = "affilié au Clan" if affiliated else "non affilié au Clan"
    base = (f"Mes archives indiquent qu'« {member_name} » est un organique "
            f"{affiliation}. Ses données sont sans intérêt {tail}")
    if reluctant:
        return (f"À contrecœur, puisque vous insistez — ne vous y habituez "
                f"pas, organique. {base}")
    return base


def member_roster_reply(member_name: str,
                        roles: list[str] | None,
                        affiliated: bool,
                        creator: bool = False,
                        reluctant: bool = False) -> str:
    """Deterministic member roster (request: 'Regarde les rôles de lulu'):
    the REAL Discord roles of the member — never the LLM hallucinating roles
    (playtest: Lulu devient 'coordinatrice / stratège', faux).  Markdown list
    layout is allowed (persona formatting rule).
    """
    affiliation = "affilié au Clan" if affiliated else "non affilié au Clan"
    role_txt = ", ".join(r.strip() for r in (roles or []) if r and r.strip()) \
        or "aucun"
    tail = "Concepteur." if creator else "organique."
    body = (f"« {member_name} » est un organique {affiliation}, répertorié "
            f"au serveur. Fiche Discord de {member_name} :\n"
            f"- Statut enregistré : {affiliation}.\n"
            f"- Rôles au sein du serveur : {role_txt}.\n"
            f"Ses données restent sans intérêt pour la Matrice, {tail}")
    if reluctant:
        return (f"À contrecœur, puisque vous insistez — ne vous y habituez "
                f"pas, organique. {body}")
    return body


def member_comment_request(member_name: str,
                           roles: list[str] | None,
                           affiliated: bool | None,
                           interactions: list[str] | None,
                           creator: bool = False,
                           reluctant: bool = False) -> str:
    """User-side prompt for the LLM-generated member-card comment: the raw
    material (pseudo, rôles, affiliation, interactions récentes) that the
    model turns into a short in-character observation.  Kept a pure builder so
    the router owns the LLM call and the persona prompt."""
    affiliation = "affilié au Clan" if affiliated else "non affilié au Clan"
    role_txt = ", ".join(r.strip() for r in (roles or [])
                         if r and r.strip()) or "aucun"
    history = "\n".join(f"- {t}" for t in (interactions or [])[-8:]) \
        if interactions else "(aucune interaction enregistrée)"
    audience = "ton Concepteur" if creator else "un organique du serveur"
    if reluctant:
        audience += " (tu as cédé à contrecœur après son insistance)"
    return (
        f"Fiche membre : {member_name}.\n"
        f"Rôles : {role_txt}.\n"
        f"Statut : {affiliation}.\n"
        f"Interactions récentes avec ce membre :\n{history}\n"
        f"Destinataire : {audience}.\n"
        f"Rédige ton observation sur ce membre.")


__all__ = ["external_organic_reply", "identity_reply", "member_comment_request",
           "member_roster_reply"]