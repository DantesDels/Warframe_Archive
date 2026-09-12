# warframe_lore/discord/abuse_manager.py
"""Escalade pénalisée par durée forcée (timeout Discord).

ÉTAGE 1 — HARD-LIMIT PROGRESSIVE (``register``) : ``BurstGuard`` (guards.py)
se contente de logs « Temporary block on abuse » que l'utilisateur ignore —
trop laxiste.  ICI : 4 infractions CONSÉCUTIVES (Spam, ``toxic_critical`` du
garde sémantique, ou Insultes) dans la fenêtre glissante de 3 minutes
⇒ ``await member.timeout(datetime.timedelta(hours=1),
reason="Violation des directives du Cephalon")``, quoi que disent les autres
compteurs.  « consécutives » = aucune ``register_pass`` (message licite
accepté) entre les faits ; la fenêtre expire aussi la série.
Fallback : si les permissions de timeout manquent (``discord.Forbidden``),
mute via le rôle « Silenced » (créé/réutilisé), toujours avec log CRITICAL.

ÉTAGE 2 — TOLÉRANCE ZÉRO (``hard_sanction``) : un verdict ``TOXIC_CRITICAL``
grave déclenche IMMÉDIATEMENT le ``Member.timeout()`` de 24 heures, sans
réponse textuelle, + rapport automatique en MP au Créateur.

Invariants : le Concepteur est protégé par son snowflake (jamais de timeout,
jamais de rapport le visant) ; tous les appels Discord sont ``async`` et
tolèrent ``Forbidden`` / ``HTTPException`` ⇒ log CRITICAL, jamais de crash
du HOC depuis un événement d'abus.

Module testable : horloge et mécanisme de timeout injectables (comme
``_clock`` de :class:`BurstGuard`).
"""

from __future__ import annotations

import datetime
import logging
import time
from collections.abc import Callable
from typing import Any

import discord
from discord import utils as discord_utils

log = logging.getLogger("warframe_lore.discord.abuse_manager")

WINDOW_SECONDS = 180.0      # fenêtre de récidive : 3 minutes
THRESHOLD = 4               # infractions consécutives avant hard-limit
TIMEOUT_TURNS = datetime.timedelta(hours=1)   # sanction : 1 heure
TIMEOUT_SECONDS = int(TIMEOUT_TURNS.total_seconds())
TIMEOUT_REASON = "Violation des directives du Cephalon"
ROLE_MUTE_NAME = "Silenced"     # fallback quand le timeout est interdit
HARD_TIMEOUT_SECONDS = 86400    # tolérance zéro : 24 heures
HARD_TIMEOUT_REASON = ("Oracle : violation majeure (insulte raciale ou "
                       "homophobe grave, apologie du terrorisme ou du nazisme) "
                       "— quarantaine de 24 heures, sans réponse.")

# Appels du timeout : durée portée en ``datetime.timedelta`` (conforme à
# l'API Discord), via ``member.timeout`` ou l'injectable ``_timeout``.
TimeoutCallable = Callable[..., Any]


class AbuseManager:
    """Limite dure anti-récidive : timeout Discord après recueil de faits.

    .. note::
       ``_clock`` et ``_timeout`` sont injectables pour des tests déterministes
       sans réseau ; par défaut ils utilisent ``time.monotonic`` et
       ``member.timeout``.
    """

    def __init__(
        self,
        window: float = WINDOW_SECONDS,
        threshold: int = THRESHOLD,
        timeout_seconds: int = TIMEOUT_SECONDS,
        reason: str = TIMEOUT_REASON,
        protected_ids: set[str] | None = None,
        _clock: Callable[[], float] = time.monotonic,
        _timeout: TimeoutCallable | None = None,
    ) -> None:
        self.window = window
        self.threshold = threshold
        self.timeout_seconds = timeout_seconds
        self.reason = reason
        self.protected_ids = set(protected_ids or ())
        self._clock = _clock
        self._timeout = _timeout
        # Compteur de récidive : user_id -> (compte, horodatage de la première infraction)
        self._streaks: dict[int, tuple[int, float]] = {}
        # Compteurs de sanction — séparés (SOLID) : progressive (1 h) et
        # tolérance zéro (24 h) vivent chacune leur vie.
        self._sanctioned_until: dict[int, float] = {}
        self._hard_until: dict[int, float] = {}

    # ~~~ interface publique ~~~~

    async def register(self, member: discord.Member,
                       kind: str) -> bool:
        """Hard-limit — comptage d'une infraction.

        ``kind`` ∈ {``spam``, ``toxic_critical``, ``insult``} : 4 infractions
        consécutives en moins de 3 minutes ⇒ timeout 1 h (``timedelta``) et
        fallback « Silenced » si le timeout est interdit.  Retourne ``True``
        si la sanction a été appliquée.  Ne lève JAMAIS : ``Forbidden`` /
        ``HTTPException`` sont loggées en CRITICAL et absorbées.
        """
        user_id = getattr(member, "id", None)
        if user_id is None or self.protected_ids.issuperset({str(user_id)}):
            return False
        now = self._clock()
        count, _first = self._streaks.get(user_id, (0, now))
        if now - _first > self.window:
            count = 0
        count += 1
        self._streaks[user_id] = (count, _first)
        log.debug("Abuse streak user=%s %d/%d (kind=%s)",
                  user_id, count, self.threshold, kind)
        if count >= self.threshold:
            return await self._apply_timeout(member, user_id, now)
        return False

    def register_pass(self, user_id: int) -> None:
        """Un message licite rompt la série : ``consécutif`` ne tient plus."""
        self._streaks.pop(user_id, None)
        log.debug("Streak abus rompue (pass) user=%s", user_id)

    async def hard_sanction(self, member: discord.Member, *,
                            kind: str = "toxic_critical",
                            creator: discord.Member | None = None,
                            channel_name: str = "",
                            excerpt: str = "") -> bool:
        """Étage 2 — tolérance zéro sur un verdict ``TOXIC_CRITICAL``.

        - Aucun texte n'est renvoyé à l'auteur (responsabilité de l'hôte).
        - ``member.timeout()`` de 24 heures, immédiat si le garde a classé
          la requête ; déjà muté → ``False`` (pas de double appel).
        - Rapport automatique en MP au Créateur (qui : ``channel_name`` +
          extrait + sanction appliquée) — invariant : le Créateur lui-même
          n'est jamais sanctionné ni rapporté.
        - ``Forbidden`` / ``HTTPException`` / … → log CRITICAL, jamais de
          remontée d'exception.
        """
        user_id = getattr(member, "id", None)
        if user_id is None or self.protected_ids.issuperset({str(user_id)}):
            return False
        now = self._clock()
        if now < self._hard_until.get(user_id, 0.0):
            log.debug("Sanction 24 h déjà en vigueur user=%s (répétition)",
                      user_id)
            return False
        self._hard_until[user_id] = now + HARD_TIMEOUT_SECONDS
        hard_duration = datetime.timedelta(seconds=HARD_TIMEOUT_SECONDS)
        # 1) Timeout long durée.
        try:
            if self._timeout is not None:
                await self._timeout(member, hard_duration,
                                    reason=HARD_TIMEOUT_REASON)
            else:
                await member.timeout(hard_duration,
                                     reason=HARD_TIMEOUT_REASON)
        except discord.Forbidden:
            log.critical("SANCTION 24 h ÉCHOUÉE (Forbidden) — permissions "
                         "manquantes sur user=%s", user_id)
        except discord.HTTPException as exc:
            log.critical("SANCTION 24 h ÉCHOUÉE (HTTPException) user=%s : %s",
                         user_id, exc)
        except Exception as exc:  # noqa: BLE001
            log.critical("SANCTION 24 h ÉCHOUÉE (exception) user=%s : %r",
                         user_id, exc)
        else:
            log.critical("SANCTION 24 h : timeout appliqué à user=%s "
                         "(kind=%s) — aucun texte renvoyé.", user_id, kind)
        # 2) Rapport automatique au Créateur (même si le timeout a échoué :
        #     un rapport vaut mieux que rien).
        await self._report_creator(
            member, creator=creator,
            kind=kind, channel_name=channel_name, excerpt=excerpt)
        return True

    async def _report_creator(self, member: discord.Member, *,
                              creator: discord.Member | None,
                              kind: str, channel_name: str,
                              excerpt: str) -> None:
        """MP automatique au Créateur : qui, où, quoi, sanction."""
        if creator is None:
            log.warning("Rapport de sanction impossible sans créateur "
                        "résolu (kind=%s)", kind)
            return
        name = (getattr(member, "display_name", None)
                or getattr(member, "name", "") or f"#{getattr(member, 'id', '')}")
        embed = discord.Embed(title="RAPPORT DE SANCTION IMMÉDIATE",
                              color=0x9b1c1c)
        embed.description = (
            f"**Auteur :** {name}\n"
            f"**Canal :** #{channel_name or 'inconnu'}\n"
            f"**Type :** {kind} (tolérance zéro — aucune réponse fournie)\n"
            f"**Extrait :** « {(excerpt or '—')[:200]} »\n"
            f"**Sanction :** timeout 24 h — "
            f"{time.strftime('%d/%m/%Y à %H:%M:%S')}")
        try:
            await creator.send(embed=embed)
        except discord.Forbidden:
            log.warning("Rapport au créateur impossible (DM fermés/forbidden)")
        except discord.HTTPException as exc:
            log.warning("Rapport au créateur impossible (HTTP) : %s", exc)
        except Exception as exc:  # noqa: BLE001
            log.warning("Rapport au créateur impossible : %r", exc)
        else:
            log.critical("Rapport de sanction envoyé au créateur "
                         "(user=%s, kind=%s)", getattr(member, "id", None),
                         kind)

    def reset(self, user_id: int) -> None:
        """Réinitialise compteurs et sanctions (``!reset`` / levée)."""
        self._streaks.pop(user_id, None)
        self._sanctioned_until.pop(user_id, None)
        self._hard_until.pop(user_id, None)

    @property
    def sanctioned(self) -> list[int]:
        """Snowflakes actuellement sous quarantaine (pour un audit rapide)."""
        now = self._clock()
        return [uid for uid, until in self._sanctioned_until.items()
                if now < until]

    # ~~~ mécanique interne ~~~~

    async def _apply_timeout(self, member: discord.Member,
                             user_id: int, now: float) -> bool:
        """Sanction 1 h via l'API Discord (``timedelta(hours=1)``).

        Permissions manquantes (``Forbidden``) → log CRITICAL et fallback
        mute par le rôle « Silenced » (réutilisé) — une sanction sans
        permissions ne reste JAMAIS lettre morte.

        Retourne ``True`` si une sanction a été (re)posée, ``False`` quand
        elle était déjà en vigueur (pas de double appel API).
        """
        until = now + self.timeout_seconds
        if self._sanctioned_until.get(user_id, 0.0) > now:
            log.debug("Timeout déjà posé user=%s (répétition)", user_id)
            return False
        self._sanctioned_until[user_id] = until
        duration = datetime.timedelta(seconds=self.timeout_seconds)
        try:
            if self._timeout is not None:
                await self._timeout(member, duration, reason=self.reason)
            else:
                await member.timeout(duration, reason=self.reason)
        except discord.Forbidden:
            log.critical(
                "HARD-LIMIT ÉCHOUÉ (Forbidden) user=%s — permissions de "
                "timeout absentes : fallback mute par le rôle « %s ».",
                user_id, ROLE_MUTE_NAME)
            await self._mute_by_role(member, user_id)
        except discord.HTTPException as exc:
            log.critical(
                "HARD-LIMIT ÉCHOUÉ (HTTPException) user=%s : %s — pas de "
                "rollback, le compteur de sanction reste posé.",
                user_id, exc)
        except Exception as exc:  # noqa: BLE001
            log.critical("HARD-LIMIT ÉCHOUÉ (exception) user=%s : %r",
                         user_id, exc)
        else:
            log.critical(
                "HARD-LIMIT : timeout d'une heure appliqué à user=%s "
                "(%d infractions consécutives dans la fenêtre de %.0f s).",
                user_id, self.threshold, self.window)
        return True

    async def _mute_by_role(self, member: discord.Member,
                            user_id: int) -> None:
        """Fallback quand le timeout est interdit : attribuer le rôle
        « Silenced » (les canaux muets par le rôle n'acceptent alors plus
        ses messages).  Modérément tolérant : ``Forbidden``/``HTTPException``
        sont loggées, jamais remontées."""
        guild = getattr(member, "guild", None)
        role = None
        if guild is not None:
            role = discord_utils.get(guild.roles, name=ROLE_MUTE_NAME)
        if role is None:
            log.critical("Fallback « %s » : rôle introuvable et permissions "
                         "d'administration aussi absentes (user=%s) — mute "
                         "impossible.", ROLE_MUTE_NAME, user_id)
            return
        try:
            await member.add_roles(role, reason=self.reason)
        except discord.Forbidden:
            log.critical("Fallback « %s » ÉCHOUÉ (Forbidden) user=%s",
                         ROLE_MUTE_NAME, user_id)
        except discord.HTTPException as exc:
            log.critical("Fallback « %s » ÉCHOUÉ (HTTPException) user=%s : %s",
                         ROLE_MUTE_NAME, user_id, exc)
        except Exception as exc:  # noqa: BLE001
            log.critical("Fallback « %s » ÉCHOUÉ (exception) user=%s : %r",
                         ROLE_MUTE_NAME, user_id, exc)
        else:
            log.critical(
                "Fallback : muté par le rôle « %s » (user=%s, 1 h) — "
                "raison : %s", ROLE_MUTE_NAME, user_id, self.reason)


__all__ = [
    "AbuseManager",
    "WINDOW_SECONDS",
    "THRESHOLD",
    "TIMEOUT_TURNS",
    "TIMEOUT_SECONDS",
    "TIMEOUT_REASON",
    "ROLE_MUTE_NAME",
    "HARD_TIMEOUT_SECONDS",
    "HARD_TIMEOUT_REASON",
]