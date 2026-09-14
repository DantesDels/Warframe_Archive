"""One-shot LLM member-card observation (KIM ``FRAME_COMMENT``).

The layout (avatar / pseudo / rôles / ID) is deterministic in the Discord embed
built by the bot; only the comment is model-generated, grounded in the member's
recent interactions (memory held bot-side).  Short, in-character, Cephalon-toned
— never an "ARCHIVE DU CODEX" block.  The request text is a pure builder here, so
the caller owns the LLM call and the persona prompt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...models import ChatMessage
from ...rag import strip_trailing_padding

if TYPE_CHECKING:
    from ...api.container import Container

# The comment must stay FACTUAL: no affiliation is asserted — the actual roles
# are listed and speak for themselves.
NO_AFFILIATION_RULE = ("N'affirme AUCUNE affiliation ni appartenance "
                       "au Clan : les rôles parlent d'eux-mêmes.")


def member_comment_request(member_name: str,
                           roles: list[str] | None,
                           interactions: list[str] | None,
                           creator: bool = False,
                           reluctant: bool = False) -> str:
    """User-side prompt of the comment: pseudo, REAL roles, recent
    interactions — the raw material the model turns into an observation."""
    role_txt = ", ".join(r.strip() for r in (roles or [])
                         if r and r.strip()) or "aucun"
    history = "\n".join(f"- {t}" for t in (interactions or [])[-8:]) \
        if interactions else "(aucune interaction enregistrée)"
    audience = "ton Concepteur" if creator else "un organique du serveur"
    if reluctant:
        audience += " (tu as cédé à contrecœur après son insistance)"
    return (
        f"Fiche membre : {member_name}.\n"
        f"Rôles réels : {role_txt}.\n"
        f"Interactions récentes avec ce membre :\n{history}\n"
        f"Destinataire : {audience}.\n"
        f"Rédige ton observation, fondée UNIQUEMENT sur les rôles réels et les "
        f"interactions ci-dessus. {NO_AFFILIATION_RULE}")


async def member_comment(container: Container, payload: dict) -> str:
    """One-shot LLM observation for a member card (short, in-character)."""
    user_msg = member_comment_request(
        member_name=str(payload.get("member_name", "")),
        roles=list(payload.get("member_roles") or []),
        interactions=[str(i) for i in (payload.get("interactions") or [])],
        creator=bool(payload.get("creator")),
        reluctant=bool(payload.get("reluctant")),
    )
    system = (
        container.roleplay.system_prompt + "\n\n"
        "DIRECTIVE FICHE MEMBRE : Rédige UNIQUEMENT une observation sur ce "
        "membre, en 2 à 4 phrases, au ton de Cephalon (glacial, précis, un "
        "brin dédaigneux), fondée STRICTEMENT sur ses rôles réels et ses "
        "interactions fournies ci-dessous. INTERDIT d'utiliser le format "
        "« ARCHIVE DU CODEX » : pas de titre, pas de champ, pas de « ◈ », pas "
        "de balise `>`, pas de liste — juste tes phrases. N'AFFIRME aucune "
        "affiliation ni appartenance au Clan que ses rôles ne montrent pas. "
        "Jamais de formule figée, jamais de salutation, aucune simulation "
        "d'action."
    )
    messages = [ChatMessage("system", system),
                ChatMessage("user", user_msg)]
    parts: list[str] = []
    async for token in container.llm.chat_stream(messages, temperature=0.7):
        parts.append(token)
    return strip_trailing_padding("".join(parts)).strip()


__all__ = ["member_comment", "member_comment_request"]
