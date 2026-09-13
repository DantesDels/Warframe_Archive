"""Message routing towards the ENGRAM Oracle gateway.

Single responsibility (mixin): decide whether a message is a lore question
(triggers RAG), a member question / roster query (deterministic answers from
the real Discord data), a creator mention (jealousy), an introspection or a
free chat — then stream the reply over one WS session per channel, serialised
per channel, interruptible by ``!stop``.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from warframe_lore.engram.rag.probes import is_self_reflection

from ..guild import (
    creator_mentioned,
    is_member_question,
    normalize_mentions,
    roles_question,
    self_info_request,
)
from ..moderation.insults import detect_insult
from ..services.gateway import RoleplayGateway
from ..services.streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.bot.routing")

# Trigger words for a document-based question (triggers a RAG retrieval).
# Bilingual FR/EN: the Oracle understands English input too.
_LORE_TRIGGERS = (
    "qui ", "qu'est", "quel", "quelle", "quand", "où ", "comment",
    "pourquoi", "combien", "histoir", "lore", "orokin", "tenno",
    "warframe", "primordial", "hex", "void", "kuva", "infest",
    "fragments", "chimer", "trésors", "règne",
    # English equivalents
    "who ", "what ", "when ", "where ", "why ", "which ", "whose ",
    "how ", "how many", "how much", "tell me about", "history",
    "who 's", "what 's", "when 's", "where 's",
)

# Bourne du cache des refus d'accès (membre-refusés par utilisateur) : les
# tables voltaïles ne peuvent pas croître avec le nombre total d'organiques.
_MAX_MEMBER_REFUSALS = 2048


class RoutingMixin:
    """Routage vers l'Oracle : gating RAG, organiques externes, streaming."""

    async def _route_to_oracle(self, message: discord.Message) -> None:
        """Streams an Oracle reply, serialised per channel and stoppable
        (``!stop``): while a turn is active, the other messages wait their
        turn — no more interleaved fragments."""
        channel_id = message.channel.id
        text = self._normalize_message(message)
        lock = self._route_locks.setdefault(channel_id, asyncio.Lock())
        async with lock:
            placeholder = None
            streamer = None
            gateway = self._gateways.get(channel_id)
            self._turns[channel_id] = asyncio.current_task()
            try:
                if gateway is None or not gateway.active:
                    if gateway is not None:
                        await gateway.close()
                    gateway = RoleplayGateway(self.gateway_url)
                    await gateway.open()
                    self._gateways[channel_id] = gateway
                use_rag = self._wants_lore(text)
                # Guild-member resolution (external-organics protocol): a
                # pseudo naming a REAL Discord member (exact or prefix
                # abbreviation, "@Aze07" or "Aze") is never a lore question —
                # the archives must never reply "Données insuffisantes".  The
                # subject question gets a deterministic disdainful answer
                # (router ``member_name``); a passing mention stays free chat
                # (persona GESTION DES ORGANIQUES EXTERNES), still RAG-free.
                member_name, member_token, subject_is_creator, member = (
                    self._resolve_member(message, text))
                if member_token:
                    use_rag = False
                    self._remember_member(channel_id, member_name, member)
                # The Concepteur is NEVER an external organic — a question
                # naming him ("Qui est DantesDels ?") must not reach the
                # deterministic outsider-disdain path, it feeds the jealousy.
                member_ask = (member_name if (member_token
                                              and not subject_is_creator
                                              and is_member_question(
                                                  text, member_token))
                              else None)
                # Roster queries ("rôles de lulu", "ses rôles") answer from
                # the REAL Discord roles — never the hallucinating LLM.
                roles_target = roles_question(text, member_token)
                roster = None
                if roles_target == "last":
                    roster = self._last_member.get(channel_id)
                elif roles_target and member is not None:
                    roster = self._member_roster(member_name, member)
                user_name, user_role, user_id = self._get_metadata(message)
                user_roles = self._role_names(message.author)
                accr = self._accredit(message.author)
                # SELF-REPORT: "mon rapport", "ma fiche", or the Concepteur
                # naming himself ("le rapport de DantesDels") → the speaker's
                # OWN matriciel card (never the devotion litany, never the
                # jealousy path).
                self_report = False
                if self_info_request(text):
                    self_report = True
                    member = message.author
                    member_name = (getattr(member, "display_name", None)
                                   or getattr(member, "name", "") or "").strip()
                    subject_is_creator = accr.creator
                elif (member_token and subject_is_creator and accr.creator
                      and is_member_question(text, member_token)):
                    self_report = True
                # JEALOUSY (decision taken): a non-Creator member citing the
                # Concepteur's pseudonym — ANY spelling or casing ("dantes",
                # "Dels", "DANTEs") — triggers possessive rage performed by
                # the LLM (persona + injected directive).  RAG stays OFF so
                # the archives never bury the mood under "[Archives] Données
                # insuffisantes"; the cited word is forwarded for injection.
                creator_mention = None
                if not accr.creator:
                    creator_display = self._creator_display(message)
                    creator_mention = creator_mentioned(
                        text, creator_display) if creator_display else None
                if creator_mention:
                    use_rag = False
                # MEMBER-INFO GATE (directive Concepteur): member data ("qui
                # est X", "rôles de X", "ses rôles") is Creator privilege.
                # A non-Creator is refused once, then concedes à contrecœur if
                # he insists on the SAME member.  The answer is a Discord
                # EMBED card (avatar, pseudo, rôles, ID, niveau de sécurité,
                # indice de fiabilité) + an LLM behavioural analysis grounded
                # in the member's recorded interactions.
                if member_ask or roster or self_report:
                    info = (dict(roster) if roster is not None
                            else self._member_roster(member_name, member))
                    if info is None:
                        info = {"display": member_name, "roles": [],
                                "affiliated": self._affiliation(member),
                                "status": None, "avatar": "",
                                "member_id": ""}
                    if not accr.creator:
                        key = (info["display"] or "").lower()
                        pocket = self._member_refusals.setdefault(
                            user_id or 0, {})
                        if len(self._member_refusals) > _MAX_MEMBER_REFUSALS:
                            self._member_refusals.pop(
                                next(iter(self._member_refusals)))
                        strikes = pocket.get(key, 0) + 1
                        pocket[key] = strikes
                        if strikes == 1:
                            log.info(
                                "Oracle member-info refused channel=%s "
                                "user=%s member=%s (non-Créateur, 1re demande)",
                                channel_id, user_id, info["display"])
                            await message.channel.send(
                                "Requête refusée, organique. Ces registres "
                                "relèvent de mon Concepteur, et de lui seul. "
                                "Votre tentative est consignée — insistez si "
                                "vous l'osez.")
                            return
                        pocket.pop(key, None)
                        info["reluctant"] = True
                    else:
                        info["reluctant"] = False
                    await self._send_member_card(gateway, message, info,
                                                 accr.creator)
                    return
                # Request audit (scan-friendly): one INFO line per handled
                # turn, with the routing decision.  "scanne les requêtes"
                # — les logs runtime ne traçaient RIEN par message.
                if accr.creator and detect_insult(text):
                    turn_kind = "creator_insult(sado-maso)"
                elif creator_mention:
                    turn_kind = "creator_mention"
                elif member_token:
                    turn_kind = "member_mention"
                elif is_self_reflection(text):
                    turn_kind = "introspection"
                elif use_rag:
                    turn_kind = "lore"
                else:
                    turn_kind = "free"
                log.info(
                    "Oracle turn channel=%s user=%s creator=%s rag=%s "
                    "kind=%s member=%s jealousy=%s text=%r",
                    channel_id, user_id, accr.creator, use_rag, turn_kind,
                    member_name or member_token, creator_mention, text[:200])
                typing_task = asyncio.create_task(self._keep_typing(message))
                placeholder = await message.channel.send("*Oracle réfléchit…*")
                streamer = MessageStreamer(placeholder)
                try:
                    try:
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag, user_name=user_name,
                                           user_role=user_role,
                                           user_id=user_id,
                                           role_status=accr.status,
                                           creator=accr.creator,
                                           user_roles=user_roles,
                                           creator_mention=creator_mention)
                    except ConnectionError as exc:
                        # Dead stream (e.g. ENGRAM server restarted) →
                        # reconnect + buffer purge (no concatenation of
                        # fragments from the previous attempt).
                        log.warning(
                            "Oracle connection lost (%s) — reconnecting", exc)
                        await gateway.close()
                        gateway = RoleplayGateway(self.gateway_url)
                        await gateway.open()
                        self._gateways[channel_id] = gateway
                        streamer.reset()
                        await gateway.send(text, on_token=streamer.add,
                                           rag=use_rag, user_name=user_name,
                                           user_role=user_role,
                                           user_id=user_id,
                                           role_status=accr.status,
                                           creator=accr.creator,
                                           user_roles=user_roles,
                                           creator_mention=creator_mention)
                finally:
                    typing_task.cancel()
            except asyncio.CancelledError:
                # Interruption requested (!stop): cut the WS stream to stop
                # the LLM generation server-side, then finalise the waiting
                # message.
                log.info("Oracle turn interrupted on channel %s", channel_id)
                if gateway is not None:
                    await gateway.close()
                    self._gateways.pop(channel_id, None)
                if streamer is not None and placeholder is not None:
                    await placeholder.edit(
                        content=f"{streamer.text or '*aucun texte*'}"
                                "\n*… réponse interrompue.*")
                    placeholder = None
                raise
            finally:
                self._turns.pop(channel_id, None)
            if streamer is not None:
                await streamer.finish()
                if (not streamer._parts
                        and placeholder is not None
                        and placeholder.content == "*Oracle réfléchit…*"):
                    if not gateway.active:
                        await placeholder.edit(
                            content="*Oracle est injoignable — serveur "
                                    "ENGRAM éteint.*")
                    else:
                        await placeholder.delete()

    def _strip_mention(self, text: str) -> str:
        """Remove the user-to-bot mention (``@Oracle …``)."""
        if self.user is None:
            return text
        mention_id = str(self.user.id)
        return (text.replace(f"<@{mention_id}>", "")
                    .replace(f"<@!{mention_id}>", "").strip())

    def _normalize_message(self, message: discord.Message) -> str:
        """Clean authoritative text of a message: bot mention removed, then
        real guild-member mentions replaced by their display name.

        The replacement happens BEFORE the hostile probe: a legitimate
        "@Aze07" is an accreditation reference, not an echo-ping attack — the
        probe's third-party-mention rule must not fire on a real member.  The
        same normalized text also feeds the member resolution and the Router.
        """
        text = self._strip_mention(message.content)
        mapping: dict[str, str] = {}
        for member in getattr(message, "mentions", ()):
            if getattr(member, "bot", False):
                continue
            name = (getattr(member, "display_name", None)
                    or getattr(member, "name", "") or "").strip()
            if name:
                mapping[str(getattr(member, "id", ""))] = name
        return normalize_mentions(text, mapping)

    def _wants_lore(self, text: str) -> bool:
        """True if the input looks like a lore question (useful RAG).

        Questions about Oracle itself or its creator (introspection) NEVER
        trigger the RAG: the no-passage short-circuit would answer
        "[Archives] Données insuffisantes…" without letting the persona use
        its consciousness exception (BLOC 2 / auth banner).
        """
        if is_self_reflection(text):
            return False
        low = text.lower()
        return any(trigger in low for trigger in _LORE_TRIGGERS)

    async def _keep_typing(self, message: discord.Message) -> None:
        while True:
            await message.channel.typing()
            await asyncio.sleep(self.typing_interval)
