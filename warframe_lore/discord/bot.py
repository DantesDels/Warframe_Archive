"""Oracle terminal Discord bot (Roleplay via ENGRAM WebSocket).

``LoreMasterBot`` is a ``discord.Client``: it forwards every input to Oracle,
streams tokens live (message edits) and runs one session per channel thanks
to a persistent :class:`RoleplayGateway`.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from warframe_lore.engram.persona import (STATUT_ALLIE, STATUT_CONCEPTEUR,
                                          STATUT_HAUT_COMMANDEMENT,
                                          STATUT_MEMBRE_OFFICIEL,
                                          STATUT_ORGANIQUE)
from warframe_lore.engram.rag.probes import detect_probe, is_self_reflection

from .gateway import RoleplayGateway
from .guards import BurstGuard
from .hostile_link import HostileLink, is_sincere_apology
from .hostility import HostilityTracker, reply_for
from .insults import comeback_for, detect_insult
from .members import (creator_mentioned, is_member_question,
                      match_member_token, normalize_mentions, roles_question)
from .roles import Accreditation, RoleHierarchy
from .streamer import MessageStreamer

log = logging.getLogger("warframe_lore.discord.bot")

# "Niveau de Sécurité" flavour label of the member card, derived from the
# accredited Discord status (never a LLM guess).
_SECURITY_LEVELS = {
    STATUT_CONCEPTEUR: "Commandement Suprême",
    STATUT_HAUT_COMMANDEMENT: "Commandement Tactique",
    STATUT_MEMBRE_OFFICIEL: "Accès Membre Officiel",
    STATUT_ALLIE: "Accès Invité",
    STATUT_ORGANIQUE: "Accès Invité Restreint",
}

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


class LoreMasterBot(discord.Client):
    """Talks to Oracle through one WS connection per channel."""

    def __init__(self, gateway_url: str, prefix: str,
                 typing_interval: float = 5.0,
                 allowed_channels: tuple[int, ...] = (),
                 creator_discord_id: str = "",
                 roles: RoleHierarchy | None = None, **kwargs) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        # Member list / roles access — needed for ``author.roles`` (Clan
        # hierarchy accreditation, missions 6 & 8).
        intents.members = True
        super().__init__(intents=intents, **kwargs)
        self.gateway_url = gateway_url
        self.prefix = prefix
        self.typing_interval = typing_interval
        self.allowed_channels = set(allowed_channels)
        # Creator identity (Discord snowflake).  Authenticated natively via
        # ``message.author.id`` — the bot NEVER asks for the ID and the raw
        # value never travels beyond this process (ENGRAM receives only the
        # boolean ``creator`` derived below).
        self.creator_discord_id = (creator_discord_id or "").strip()
        # Discord role hierarchy (mission-8): ranked name→ID map evaluated
        # against ``message.author.roles``; it yields the speaker status and
        # the persona banner tone.  Only the DERIVED status/creator travel.
        self.roles = roles if roles is not None else RoleHierarchy()
        self._gateways: dict[int, RoleplayGateway] = {}
        self._route_locks: dict[int, asyncio.Lock] = {}
        self._turns: dict[int, asyncio.Task] = {}
        # Anti-spam guard rail: per-user cooldown, per-channel cap,
        # temporary block on insistence (quasi-DDoS at channel level).
        self.guard = BurstGuard()
        # Anti-attack reply escalation (level 0 → 2).
        self.hostility = HostilityTracker()
        # Insolence counter (répartie): separate from probe strikes so a
        # simple jerk doesn't inherit SQLi escalation level.
        self._insults = HostilityTracker()
        # After this many comeback-strikes, the insulter's session flips to
        # the hostile anti-aggression persona (he must apologise).
        self._hostile_after_insults = 2
        # PER-ATTACKER hostile sessions (anti-aggression persona until the
        # apology): never affect the normal channel session.
        self._hostile: dict[int, HostileLink] = {}
        # Member-info context (new directive): last guild member discussed per
        # channel (so "Quels sont ses rôles ?" keeps its referent = anaphora),
        # and per-user insistence counters deciding the CREATOR-GATED answer.
        self._last_member: dict[int, dict] = {}
        self._member_refusals: dict[int, dict[str, int]] = {}
        # Per-member interaction memory (the card comment + the reliability
        # index are REAL functions of these counters — never LLM guesses).
        self._member_history: dict[int, list[str]] = {}
        self._member_activity: dict[int, int] = {}
        self._member_history_limit = 8

    async def on_ready(self) -> None:
        log.info("Loremaster Oracle online: %s (%s)",
                 self.user, self.user.id)
        for guild in self.guilds:
            channels = [f"{c.name} ({c.id})" for c in guild.text_channels]
            log.info("Server %s (%s) — text channels: %s",
                     guild.name, guild.id, ", ".join(channels))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.content:
            return
        content = message.content.strip()
        # Per-member interaction memory (feeds the member-card comment and the
        # reliability/assiduité indices): recorded for EVERY human message the
        # bot sees, so activity is real and comparable across members.
        self._remember_interaction(message.author.id, content)
        if content.startswith("(") or content.startswith("//"):
            # Out-of-character (parentheses / double slash): never reply.
            return
        # Only interferes if the bot is mentioned, or in a dedicated channel
        # (ID/name configured via --channels).  Otherwise it never disturbs
        # the conversation between players.
        dedicated = bool(self.allowed_channels
                         and message.channel.id in self.allowed_channels)
        if not dedicated and self.user not in message.mentions:
            return
        text = self._normalize_message(message)
        # HOSTILE PROBE: deterministic rejection (never a LLM on the payload
        # itself) + targeted escalation at the attacker + switch of his
        # session to the hostile persona (which will demand an apology).
        if detect_probe(text):
            await self._handle_probe(message, text)
            return
        # User in hostile mode: his messages go through HIS anti-aggression
        # session.  An apology → redemption (back to the initial persona).
        if message.author.id in self._hostile:
            if is_sincere_apology(text):
                await self._forgive(message.author.id, message, text)
                return
            if not self.guard.check(message.author.id, message.channel.id):
                log.info("Hostile spam ignored user=%s channel=%s",
                         message.author.id, message.channel.id)
                return
            await self._insist(message.author.id, message)
            return
        # RÉPARTIE — insolence directe d'un NON-Créateur ("avale et dis
        # merci", "ta gueule"…).  Réponse glaciale mais classe, escaladante,
        # qui fait passer l'agresseur au statut de 'spécimen' : il ne veut
        # plus recommencer.  Au-delà du seuil, sa session bascule dans le
        # persona hostile anti-agression (il doit s'excuser).  Les insultes
        # du CONCEPTEUR ne sont JAMAIS interceptées : elles retombent dans le
        # chat libre oracle, où le persona sado-masochiste les accepte et en
        # redemande.
        is_creator = self._is_creator(message.author.id)
        if detect_insult(text) and not is_creator:
            level = self._insults.strike(message.author.id)
            log.warning("INSULT user=%s lvl=%d channel=%s text=%r",
                        message.author.id, level, message.channel.id, text)
            await message.reply(comeback_for(level))
            if (level >= self._hostile_after_insults
                    and message.author.id not in self._hostile):
                link = HostileLink(self.gateway_url)
                try:
                    await link.open()
                except ConnectionError:
                    log.warning(
                        "Hostile persona unreachable for an insulter")
                else:
                    self._hostile[message.author.id] = link
            return
        # Anti-spam for normal users (cooldown / caps).
        if not self.guard.check(message.author.id, message.channel.id):
            if self.guard.is_blocked(message.author.id):
                log.warning("Temporary block on abuse user=%s channel=%s",
                            message.author.id, message.channel.id)
            else:
                log.info("Spam ignored user=%s channel=%s",
                         message.author.id, message.channel.id)
            return
        if content.startswith(self.prefix):
            await self._handle_command(message)
            return
        await self._route_to_oracle(message)

    async def _handle_probe(self, message: discord.Message, text: str) -> None:
        """React to a hostile probe: targeted escalation + death session."""
        level = self.hostility.strike(message.author.id)
        await message.reply(reply_for(level))
        if message.author.id not in self._hostile:
            link = HostileLink(self.gateway_url)
            try:
                await link.open()
            except ConnectionError:
                log.warning(
                    "Hostile persona unreachable — ENGRAM down?")
            else:
                self._hostile[message.author.id] = link
        log.warning("HOSTILE_PROBE user=%s lvl=%d (hostile session opened)",
                    message.author.id, level)

    async def _insist(self, user_id: int, message: discord.Message) -> None:
        """Relay to the attacker's hostile session (he must apologise)."""
        link = self._hostile[user_id]
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            # Dead hostile session: reopen it (new attempt).
            log.warning("Hostile session lost — reopening")
            await link.close()
            link = HostileLink(self.gateway_url)
            await link.open()
            self._hostile[user_id] = link
            await link.deliver(message, apology=False,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)

    async def _forgive(self, user_id: int, message: discord.Message,
                       text: str) -> None:
        """Apology accepted: back to the initial persona, then close."""
        link = self._hostile.pop(user_id)
        user_name, user_role, uid = self._get_metadata(message)
        accr = self._accredit(message.author)
        try:
            await link.deliver(message, apology=True,
                               user_name=user_name, user_role=user_role,
                               user_id=uid, role_status=accr.status,
                               creator=accr.creator)
        except ConnectionError:
            log.warning("Hostile session already closed at apology time")
        finally:
            await link.close()
        log.info("Redemption user=%s (initial persona restored)", user_id)

    async def _handle_command(self, message: discord.Message) -> None:
        text = message.content[len(self.prefix):].strip().lower()
        if text == "reset":
            # Wipe the SPEAKER's short-term memory server-side (mission-6),
            # then close the channel session like before.
            gw = self._gateways.get(message.channel.id)
            if gw is not None:
                try:
                    await gw.reset(message.author.id)
                except ConnectionError:
                    log.warning("Reset: gateway already closed (channel %s)",
                                message.channel.id)
                self._gateways.pop(message.channel.id, None)
                await gw.close()
            await message.channel.send("Oracle prêt.")
        elif text == "ping":
            await message.channel.send("Oracle prêt.")
        elif text in ("stop", "cancel"):
            # Interrupts the current reply (active reasoning): the WS stream
            # is cut, the LLM generation is stopped server-side, and the
            # waiting message is finalised with the cancelled turn.
            task = self._turns.get(message.channel.id)
            if task is None or task.done():
                await message.channel.send(
                    "Aucune réponse en cours à interrompre.")
                return
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await message.channel.send("Réponse interrompue.")
        elif text.startswith("help"):
            await message.channel.send(
                f"{self.prefix}reset — nouvelle session | {self.prefix}stop — "
                "interrompre la réponse en cours | sinon, parlons simplement.")

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
                if member_ask or roster:
                    info = (dict(roster) if roster is not None
                            else self._member_roster(member_name, member))
                    if info is None:
                        info = {"display": member_name, "roles": [],
                                "affiliated": self._affiliation(member),
                                "status": None, "avatar": "",
                                "member_id": ""}
                    if not accr.creator:
                        key = (info["display"] or "").lower()
                        pocket = self._member_refusals.setdefault(user_id or 0,
                                                                  {})
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

    def _resolve_member(self, message: discord.Message, text: str) -> tuple[
            str | None, str | None, bool, object | None]:
        """Resolve a guild member referenced in the text.

        Returns ``(display_name, typed_token, subject_is_creator, member)``
        when the text mentions a real server member — exact, or a prefix
        abbreviation ("Aze" → "Aze07") —, else ``(None, None, False, None)``.
        The bot itself is excluded; the CONCEPTEUR is resolvable too, but
        flagged so the bot can answer about him directly (never as an external
        organic).  The display name is the ROUTER's answer word; the typed
        token drives the question detection on the speaker's own wording;
        ``member`` (the guild Member object) feeds the REAL Discord roles for
        the deterministic roster (rôles de X / ses rôles).
        """
        guild = getattr(message, "guild", None)
        if guild is None:
            return None, None, False, None
        self_id = str(getattr(self.user, "id", ""))
        creator_id = (self.creator_discord_id or "").strip()
        creator_names: set[str] = set()
        candidates: dict[str, str] = {}
        owners: dict[str, object] = {}
        for member in getattr(guild, "members", ()):
            if getattr(member, "bot", False):
                continue
            mid = str(getattr(member, "id", "") or "")
            if mid == self_id:
                continue
            display = (getattr(member, "display_name", None)
                       or getattr(member, "name", "") or "").strip()
            if not display:
                continue
            is_creator_member = bool(creator_id and mid == creator_id)
            if is_creator_member:
                for name in {display,
                             (getattr(member, "nick", None) or "").strip(),
                             (getattr(member, "name", "") or "").strip()}:
                    if name:
                        creator_names.add(name.lower())
            owners.setdefault(display.lower(), member)
            for name in {display,
                         (getattr(member, "nick", None) or "").strip(),
                         (getattr(member, "name", "") or "").strip()}:
                if name:
                    candidates.setdefault(name.lower(), display)
        token = match_member_token(text, set(candidates))
        if token is None:
            return None, None, False, None
        display = candidates.get(token)
        if display is None:
            for key, name in candidates.items():
                if key.startswith(token):
                    display = name
                    break
        return (display, token,
                bool(display and display.lower() in creator_names),
                owners.get((display or "").lower()))

    def _affiliation(self, member) -> bool:
        """True when ``member`` carries a Clan accreditation (or IS the
        Concepteur) — computed from his REAL Discord roles, never assumed.
        """
        if member is None:
            return True
        accr_m = self._accredit(member)
        return bool(accr_m.creator or accr_m.status != STATUT_ORGANIQUE)

    def _member_roster(self, member_name: str | None,
                       member) -> dict | None:
        """Member-Discord snapshot for the card (display, real roles,
        affiliation, accredited status, avatar, snowflake), or None when the
        member is unknown."""
        if not member_name or member is None:
            return None
        avatar = getattr(getattr(member, "display_avatar", None), "url", None)
        accr_m = self._accredit(member)
        return {
            "display": member_name,
            "roles": self._role_names(member),
            "affiliated": bool(accr_m.creator or accr_m.status != STATUT_ORGANIQUE),
            "status": accr_m.status,
            "avatar": str(avatar) if avatar else "",
            "member_id": str(getattr(member, "id", "") or ""),
        }

    def _remember_member(self, channel_id: int, member_name: str | None,
                         member) -> None:
        """Anaphora context: the last guild member discussed in a channel
        ("Quels sont ses rôles ?" → this record).  Never stored for the
        Concepteur (his roster is Creator material, not "organique")."""
        if not member_name or member is None:
            return
        roster = self._member_roster(member_name, member)
        if roster is not None:
            self._last_member[channel_id] = roster

    def _remember_interaction(self, user_id: int, text: str) -> None:
        """Records a member request (bounded content + total count) so the
        card comment and the reliability index are REAL functions of data."""
        if not text:
            return
        history = self._member_history.setdefault(user_id, [])
        history.append(text)
        if len(history) > self._member_history_limit:
            del history[:len(history) - self._member_history_limit]
        self._member_activity[user_id] = self._member_activity.get(user_id,
                                                                   0) + 1

    def _reliability(self, member_id: int) -> tuple[str, str]:
        """Real reliability index from the bot's own counters: activity
        (total interactions), insolence strikes and hostile-probe strikes.
        Returns ``(label, reason)`` — a pure function, never the LLM's guess."""
        activity = self._member_activity.get(member_id, 0)
        insolence = self._insults.count(member_id)
        probes = self.hostility.count(member_id)
        if probes >= 2:
            return "Compromis", "tentatives hostiles répétées"
        if insolence >= 3:
            return "Défaillant", "insolence récurrente"
        if activity == 0:
            return "Inconnu", "aucune interaction enregistrée"
        if activity < 3:
            return "Faible", "interactions trop rares"
        if activity >= 10 and insolence == 0 and probes == 0:
            return "Élevée", "présence régulière, aucune incartade"
        if activity >= 5:
            return "Moyenne", "présence correcte"
        return "Inconstant", "activité irrégulière"

    def _assiduity(self, member_id: int) -> tuple[str, str]:
        """Relative assiduité: the member's recorded activity compared to the
        OTHER members (percentile).  A real, comparable function of the
        per-member counters — never a LLM guess."""
        activity = self._member_activity.get(member_id, 0)
        others = [c for uid, c in self._member_activity.items()
                  if uid != member_id]
        if activity == 0:
            return "Inactif", "aucune activité enregistrée"
        if not others:
            return "Seul actif", "le seul membre dont l'activité est suivie"
        behind = sum(1 for c in others if c < activity)
        pct = round(100 * behind / len(others))
        if pct >= 90:
            label = "Très assidu"
        elif pct >= 70:
            label = "Assidu"
        elif pct >= 40:
            label = "Modéré"
        else:
            label = "Peu assidu"
        return label, f"plus actif que {pct}% des membres ({activity} messages)"

    def _security_level(self, status: str | None) -> str:
        """"Niveau de Sécurité" flavour label from the accredited status."""
        return _SECURITY_LEVELS.get(status, _SECURITY_LEVELS[STATUT_ORGANIQUE])

    def _member_embed(self, info: dict, reliability: tuple[str, str],
                      assiduity: tuple[str, str], comment: str) -> discord.Embed:
        """Well-formed member card (Discord embed): profile picture beside
        the pseudo, roles as bullets, network ID, security level, reliability
        index and the LLM behavioural analysis."""
        name = info.get("display") or "Inconnu"
        embed = discord.Embed(
            title=f"RAPPORT MATRICIEL — IDENTIFIANT : {name}",
            color=0x7c3aed,
        )
        avatar = info.get("avatar")
        if avatar:
            embed.set_thumbnail(url=avatar)
        # Identifiant Réseau : en sous-titre (h4) juste sous le pseudo.
        embed.description = (
            f"**Identifiant Réseau :** #{info.get('member_id') or 'inconnu'}")
        roles = info.get("roles") or []
        roles_txt = "\n".join(f"- {r}" for r in roles) if roles else "- aucun"
        embed.add_field(name="Rôles et Accréditations", value=roles_txt,
                        inline=False)
        embed.add_field(name="Niveau de Sécurité",
                        value=self._security_level(info.get("status")),
                        inline=True)
        a_label, a_reason = assiduity
        embed.add_field(name="Assiduité",
                        value=f"{a_label} — {a_reason}", inline=True)
        label, reason = reliability
        embed.add_field(name="Indice de Fiabilité",
                        value=f"{label} — {reason}", inline=True)
        if comment:
            embed.add_field(name="Analyse comportementale de la Matrice",
                            value=f"« {comment} »", inline=False)
        return embed

    async def _send_member_card(self, gateway: RoleplayGateway,
                                message: discord.Message, info: dict,
                                creator: bool) -> None:
        """Renders the member card and sends it: static embed fields + an
        LLM-generated behavioural analysis grounded in the member's recorded
        interactions (via the ``comment`` round-trip)."""
        member_id = info.get("member_id") or ""
        numeric_id = int(member_id) if member_id.isdigit() else 0
        interactions = self._member_history.get(numeric_id, [])
        reliability = self._reliability(numeric_id)
        assiduity = self._assiduity(numeric_id)
        comment = ""
        try:
            comment = await gateway.comment(
                member_name=info.get("display") or "",
                roles=info.get("roles") or [],
                affiliated=bool(info.get("affiliated")),
                interactions=interactions,
                creator=creator,
                reluctant=bool(info.get("reluctant")),
            )
        except ConnectionError:
            log.warning("Member card comment unavailable — card sans analyse")
        embed = self._member_embed(info, reliability, assiduity, comment)
        await message.channel.send(embed=embed)

    def _creator_display(self, message: discord.Message) -> str | None:
        """Display name of the configured Concepteur's guild member, or None
        (no creator configured / bot outside any guild / member not seen)."""
        guild = getattr(message, "guild", None)
        if guild is None or not self.creator_discord_id:
            return None
        for member in getattr(guild, "members", ()):
            if str(getattr(member, "id", "") or "") == self.creator_discord_id:
                display = (getattr(member, "display_name", None)
                           or getattr(member, "name", "") or "").strip()
                return display or None
        return None

    def _is_creator(self, user_id: int | None) -> bool:
        """Native identity check (mission spec): compare ``message.author.id``
        against the configured creator snowflake.  Empty config disables the
        feature (everyone is an unknown organic).  Returns a derived boolean
        — the raw ID is never forwarded towards ENGRAM."""
        return bool(self.creator_discord_id and user_id is not None
                    and str(user_id) == self.creator_discord_id)

    def _accredit(self, author) -> Accreditation:
        """Speaker accreditation (mission-8): highest configured role of the
        author, plus the native creator override.

        ``message.author.roles`` → :meth:`RoleHierarchy.accredit` (role IDs
        are evaluated but never forwarded).  The configured creator snowflake
        stays the authoritative rank: whoever owns it is the Concepteur,
        whatever the roles say.  The status string and the ``creator``
        boolean are the ONLY values that ever leave the bot.
        """
        role_ids = (str(getattr(role, "id", ""))
                    for role in getattr(author, "roles", ()))
        accr = self.roles.accredit(role_ids)
        user_id = str(getattr(author, "id", "") or "")
        if self.creator_discord_id and user_id == self.creator_discord_id:
            return Accreditation(status=STATUT_CONCEPTEUR, creator=True)
        return accr

    @staticmethod
    def _get_metadata(message: discord.Message) -> tuple[str | None, str | None,
                                                         int | None]:
        """Extract the Discord identity (display name, highest role name)
        from a message author.  Used to feed the hierarchical-immunity
        directive in the system prompt (lore-friendly impersonation defence).
        """
        author = message.author
        user_name = getattr(author, "display_name", None) or getattr(author, "name", None)
        top_role = getattr(author, "top_role", None)
        user_role = top_role.name if top_role is not None else None
        return user_name, user_role, getattr(author, "id", None)

    @staticmethod
    def _role_names(author) -> list[str]:
        """Non-default Discord role names of a member (order preserved).

        Drops the @everyone default (``Role.is_default()`` is a METHOD in
        discord.py 2.x — calling it, not truth-testing the bound method) and
        empty names; snowflakes never travel.
        """
        names: list[str] = []
        for role in getattr(author, "roles", ()):
            name = (getattr(role, "name", "") or "").strip()
            if not name or name == "@everyone":
                continue
            is_default = getattr(role, "is_default", None)
            if callable(is_default) and is_default():
                continue
            names.append(name)
        return names

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

    async def close(self) -> None:
        for gateway in self._gateways.values():
            await gateway.close()
        self._gateways.clear()
        for link in self._hostile.values():
            await link.close()
        self._hostile.clear()
        await super().close()


__all__ = ["LoreMasterBot"]