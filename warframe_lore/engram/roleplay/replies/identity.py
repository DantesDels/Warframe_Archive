"""Deterministic speaker-identity answers (mission-7, request from playtest).

Questions such as "qui suis-je ?" or "quel est mon rôle ?" are answered
DETERMINISTICALLY from the accredited Discord data (BLOC 2 identity) instead of
the LLM: devotion personas (CAS A) systematically self-introduce ("Je suis
Cephalon Oracle…") instead of presenting the speaker, despite every prompt
directive.  Never the archives, never the model, never a raw role snowflake.
"""

from __future__ import annotations

from ...auth import (
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


__all__ = ["identity_reply"]
