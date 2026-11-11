"""Local-stack bootstrap contract: shared by the CLI and the Discord bot.

The auto-start moved from ``warframe_lore.discord.bootstrap`` to the neutral
``warframe_lore.infra`` package so ``cephalon run`` / ``cephalon update`` use
the exact same Docker + PostgreSQL boot sequence as ``cephalon bot run``.
"""

from __future__ import annotations

import argparse
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from warframe_lore.cli import commands as cmd
from warframe_lore.cli.commands_aux import _cmd_update_impl
from warframe_lore.infra import db_bootstrap
from warframe_lore.infra import ensure_database as facade_ensure_database

DB_URL = "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore"


class EndpointTests(unittest.TestCase):
    def test_asyncpg_driver_suffix_is_stripped(self):
        self.assertEqual(db_bootstrap._endpoint(DB_URL), ("localhost", 5432))

    def test_explicit_host_and_port_are_honoured(self):
        self.assertEqual(
            db_bootstrap._endpoint("postgresql+asyncpg://db.example.com:6543/lore"),
            ("db.example.com", 6543),
        )


class EnsureDatabaseTests(unittest.TestCase):
    def test_reachable_port_skips_engine_and_stack(self):
        with (
            patch.object(db_bootstrap, "_tcp_open", return_value=True),
            patch.object(db_bootstrap, "ensure_engine") as ensure_engine,
            patch.object(db_bootstrap, "_start_stack") as start_stack,
        ):
            db_bootstrap.ensure_database(DB_URL)
        ensure_engine.assert_not_called()
        start_stack.assert_not_called()

    def test_cold_port_starts_engine_then_stack(self):
        with (
            patch.object(db_bootstrap, "_tcp_open", side_effect=[False, True]),
            patch.object(db_bootstrap, "ensure_engine") as ensure_engine,
            patch.object(db_bootstrap, "_start_stack") as start_stack,
            patch.object(db_bootstrap, "wait_until", return_value=True) as wait,
        ):
            db_bootstrap.ensure_database(DB_URL)
        ensure_engine.assert_called_once_with()
        start_stack.assert_called_once_with()
        wait.assert_called_once()

    def test_remote_host_is_never_booted(self):
        with (
            patch.object(db_bootstrap, "_tcp_open") as tcp_open,
            patch.object(db_bootstrap, "ensure_engine") as ensure_engine,
            patch.object(db_bootstrap, "_start_stack") as start_stack,
        ):
            db_bootstrap.ensure_database(
                "postgresql+asyncpg://db.example.com:5432/warframe_lore")
        tcp_open.assert_not_called()
        ensure_engine.assert_not_called()
        start_stack.assert_not_called()

    def test_unreachable_port_raises_after_waiting(self):
        with (
            patch.object(db_bootstrap, "_tcp_open", return_value=False),
            patch.object(db_bootstrap, "ensure_engine"),
            patch.object(db_bootstrap, "_start_stack"),
            patch.object(db_bootstrap, "wait_until", return_value=False),
        ):
            with self.assertRaises(RuntimeError):
                db_bootstrap.ensure_database(DB_URL)


class RunCommandBootstrapTests(unittest.TestCase):
    def _args(self, *, skip_sql: bool = False) -> argparse.Namespace:
        return argparse.Namespace(
            force=False,
            skip_sql=skip_sql,
            no_ui=True,
            database_url=None,
            bucket_config=None,
            verbose=False,
        )

    def _config(self) -> SimpleNamespace:
        return SimpleNamespace(database_url=DB_URL, output_dir="out")

    def test_run_bootstraps_the_database(self):
        with (
            patch("warframe_lore.cli.commands.build_config",
                  return_value=(self._config(), None)),
            patch("warframe_lore.cli.commands.build_scraper") as build_scraper,
            patch("warframe_lore.cli.commands.ensure_database") as ensure,
        ):
            self.assertEqual(cmd._cmd_run(self._args()), 0)
        ensure.assert_called_once_with(DB_URL)
        build_scraper.return_value.run.assert_called_once_with(force=False)

    def test_skip_sql_never_bootstraps_the_database(self):
        with (
            patch("warframe_lore.cli.commands.build_config",
                  return_value=(self._config(), None)),
            patch("warframe_lore.cli.commands.build_scraper"),
            patch("warframe_lore.cli.commands.ensure_database") as ensure,
        ):
            self.assertEqual(cmd._cmd_run(self._args(skip_sql=True)), 0)
        ensure.assert_not_called()


class UpdateCommandBootstrapTests(unittest.TestCase):
    def test_update_bootstraps_the_resolved_database_url(self):
        args = argparse.Namespace(database_url=None, force=False)
        with (
            patch("warframe_lore.cli.commands_aux.build_config",
                  return_value=(SimpleNamespace(database_url=DB_URL), None)),
            patch("warframe_lore.cli.commands_aux.ensure_database") as ensure,
            patch("warframe_lore.update.run.run_update",
                  new=AsyncMock(return_value={})),
        ):
            asyncio.run(_cmd_update_impl(args))
        ensure.assert_called_once_with(DB_URL)

    def test_update_uses_the_cli_override(self):
        override = "postgresql+asyncpg://warframe:warframe@localhost:5432/other"
        args = argparse.Namespace(database_url=override, force=False)
        with (
            patch("warframe_lore.cli.commands_aux.build_config",
                  return_value=(SimpleNamespace(database_url=DB_URL), None)),
            patch("warframe_lore.cli.commands_aux.ensure_database") as ensure,
            patch("warframe_lore.update.run.run_update",
                  new=AsyncMock(return_value={})),
        ):
            asyncio.run(_cmd_update_impl(args))
        ensure.assert_called_once_with(override)


class FacadeCompatibilityTests(unittest.TestCase):
    def test_bot_facade_reuses_the_neutral_bootstrap(self):
        from warframe_lore.discord.bootstrap import (  # noqa: PLC0415
            ensure_database as bot_ensure_database,
        )

        self.assertIs(bot_ensure_database, facade_ensure_database)


if __name__ == "__main__":
    unittest.main()
