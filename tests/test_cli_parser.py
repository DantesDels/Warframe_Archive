"""Contrat de la CLI ``cephalon`` : sous-commandes, options et argv legacy.

La CLI est le point d'entrée de tout (pipeline, UI, bot). Ces tests verrouillent
sa structure après découpage (`parser` racine, `subcommands/` par domaine,
`legacy` pour l'ancienne syntaxe) : mêmes commandes, mêmes options, mêmes
handlers, même réécriture des argv historiques.
"""

from __future__ import annotations

import unittest

from warframe_lore.cli import commands as cmd
from warframe_lore.cli.legacy import normalize_legacy_argv
from warframe_lore.cli.parser import build_parser

EXPECTED = {
    "run": cmd._cmd_run,
    "diff": cmd._cmd_diff,
    "status": cmd._cmd_status,
    "recent": cmd._cmd_recent,
    "buckets": cmd._cmd_buckets,
    "init-db": cmd._cmd_init_database,
    "ui": cmd._cmd_ui,
    "export-entities": cmd._cmd_export_entities,
    "kim-dm": cmd._cmd_kim_dm,
    "bot": cmd._cmd_bot,
    "version": cmd._cmd_version,
    "help": None,
}


def subparsers(parser):
    """Mapping nom -> sous-parseur d'un parser argparse."""
    for action in parser._actions:
        if hasattr(action, "choices") and isinstance(action.choices, dict):
            return action.choices
    return {}


class SubcommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = build_parser()
        self.choices = subparsers(self.parser)

    def test_toutes_les_sous_commandes_déclarées(self):
        self.assertEqual(set(self.choices), set(EXPECTED))

    def test_chaque_commande_a_son_handler(self):
        for name, handler in EXPECTED.items():
            with self.subTest(command=name):
                defaults = self.choices[name].get_default("func")
                self.assertIs(defaults, handler)

    def test_options_du_pipeline(self):
        options = {o for a in self.choices["run"]._actions
                   for o in a.option_strings}
        self.assertEqual(
            {"--force", "--skip-sql", "--no-ui", "--bucket-config",
             "--database-url"} & options,
            {"--force", "--skip-sql", "--no-ui", "--bucket-config",
             "--database-url"})

    def test_options_du_bot(self):
        run = subparsers(self.choices["bot"])["run"]
        options = {o for a in run._actions for o in a.option_strings}
        self.assertIn("--token", options)
        self.assertIn("--ws", options)
        self.assertIn("--prefix", options)
        self.assertIn("--channels", options)

    def test_langues_imposées_aux_outils(self):
        for name in ("export-entities", "kim-dm"):
            with self.subTest(command=name):
                choices = [a.choices for a in self.choices[name]._actions
                           if "--lang" in a.option_strings][0]
                self.assertIn("fr", choices)
                self.assertIn("en", choices)

    def test_parsing_d_une_commande_complète(self):
        args = self.parser.parse_args(
            ["--verbose", "run", "--force", "--skip-sql"])
        self.assertTrue(args.verbose)
        self.assertEqual(args.command, "run")
        self.assertTrue(args.force)
        self.assertIs(args.func, cmd._cmd_run)


class LegacyArgvTests(unittest.TestCase):
    def test_argv_vide_inchangé(self):
        self.assertEqual(normalize_legacy_argv([]), [])

    def test_commande_moderne_inchangée(self):
        for argv in (["status"], ["bot", "run"], ["-h"], ["--help"]):
            with self.subTest(argv=argv):
                self.assertEqual(normalize_legacy_argv(argv), argv)

    def test_drapeau_bot_historique(self):
        self.assertEqual(normalize_legacy_argv(["-bot", "run", "--verbose"]),
                         ["bot", "run", "--verbose"])
        self.assertEqual(normalize_legacy_argv(["--bot"]), ["bot"])

    def test_pipeline_historique(self):
        self.assertEqual(normalize_legacy_argv(["--force", "--skip-sql"]),
                         ["run", "--force", "--skip-sql"])

    def test_bucket_config_historique(self):
        self.assertEqual(
            normalize_legacy_argv(["--bucket-config", "buckets.json"]),
            ["run", "--bucket-config", "buckets.json"])

    def test_init_db_et_buckets_historiques(self):
        self.assertEqual(normalize_legacy_argv(["--init-db"]), ["init-db"])
        self.assertEqual(normalize_legacy_argv(["--list-buckets"]), ["buckets"])
        self.assertEqual(normalize_legacy_argv(["--init-bucket-config"]),
                         ["buckets", "--init"])

    def test_verbose_et_database_url_remontés(self):
        self.assertEqual(
            normalize_legacy_argv(["-v", "--force", "--database-url", "url"]),
            ["--verbose", "run", "--force", "--database-url", "url"])


if __name__ == "__main__":
    unittest.main()
