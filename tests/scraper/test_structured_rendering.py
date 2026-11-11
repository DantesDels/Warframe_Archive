"""Contrats des renderers : une ligne de table structurée -> (title, content).

Les renderers sont des fonctions pures (aucune DB, aucun LLM) : on vérifie
que chaque table produit un couple titre/contenu lisible, avec les champs
optionnels (description, résumé…) et les marqueurs booléens.
"""

from __future__ import annotations

import unittest

from warframe_lore.structured.rendering import (
    RENDERERS,
    render_row,
)


class RenderingTests(unittest.TestCase):
    def test_warframe_base_sans_description(self):
        title, content = render_row(
            "warframes",
            {
                "frame_name": "Ash",
                "is_prime": False,
                "description": None,
            },
        )
        self.assertEqual(title, "Ash")
        self.assertEqual(content, "Warframe: Ash")

    def test_warframe_prime_suffixe_unique(self):
        """Une seule occurrence de « Prime » : le suffixe est ajouté par le
        renderer d'après le booléen ``is_prime`` (jamais présent dans
        ``frame_name``, qui reste le nom de base)."""
        title, content = render_row(
            "warframes",
            {
                "frame_name": "Ash",
                "is_prime": True,
                "description": "Le désert regarde.",
            },
        )
        self.assertEqual(title, "Ash Prime")
        self.assertIn("Warframe: Ash Prime", content)
        # Pas de « Prime Prime » dans le contenu.
        self.assertNotIn("Prime Prime", content)
        self.assertIn("Le désert regarde", content)

    def test_quest_avec_type_et_context(self):
        title, content = render_row(
            "game_quests",
            {
                "quest_name": "The War Within",
                "quest_type": "main",
                "release_note": "released in Update 19.0",
                "quest_context": "L'éveil du Drifter.",
            },
        )
        self.assertEqual(title, "The War Within")
        self.assertIn("Quête : The War Within", content)
        self.assertIn("Type : main", content)
        self.assertIn("released in Update 19.0", content)
        self.assertIn("L'éveil du Drifter", content)

    def test_update_avec_tous_champs(self):
        title, content = render_row(
            "game_updates",
            {
                "version": "39.0.0",
                "update_title": "Techrot Encore",
                "update_type": "Mise à jour principale",
                "release_date": "Jun 25, 2025",
                "summary": "Florence, la new wave.",
            },
        )
        self.assertEqual(title, "Mise à jour 39.0.0")
        self.assertIn("Version 39.0.0", content)
        self.assertIn("Techrot Encore", content)
        self.assertIn("Jun 25, 2025", content)

    def test_annonce_sans_date(self):
        title, content = render_row(
            "game_announcements",
            {
                "title": "Devstream 200",
                "subtitle": None,
                "published_at": None,
                "summary": "Rendez-vous sur Twitch.",
            },
        )
        self.assertEqual(title, "Devstream 200")
        self.assertNotIn("Publié", content)
        self.assertIn("Rendez-vous sur Twitch", content)

    def test_lore_item_avec_narrateur_et_secret(self):
        title, content = render_row(
            "lore_items",
            {
                "item_name": "Forge",
                "series": "Glass Shard Fragments",
                "narrator": "Ballas",
                "planet": "Lua",
                "item_text": "L'Orokin forge les Warframes.",
                "secret_text": "Secret révélé.",
            },
        )
        self.assertEqual(title, "Forge (Glass Shard Fragments)")
        self.assertIn("Narrateur : Ballas", content)
        self.assertIn("Lua", content)
        self.assertIn("Texte caché : Secret révélé", content)

    def test_dialogue_kim_avec_chapitre(self):
        title, content = render_row(
            "game_dialogues",
            {
                "dialogue_kind": "kim",
                "context": "Lettie",
                "chapter": "Chapitre 1",
                "speaker": "Le Drifter",
                "message_text": "On se revoit bientôt.",
            },
        )
        self.assertEqual(title, "Lettie — Le Drifter")
        self.assertIn("[kim]", content)
        self.assertIn("Chapitre : Chapitre 1", content)
        self.assertIn("Le Drifter : On se revoit bientôt", content)

    def test_dialogue_sans_contexte_fall_back_kind(self):
        title, _ = render_row(
            "game_dialogues",
            {
                "dialogue_kind": "quote",
                "context": None,
                "chapter": None,
                "speaker": "Ballack",
                "message_text": "Merci, mon frère.",
            },
        )
        self.assertEqual(title, "quote — Ballack")

    def test_registry_couvre_les_tables(self):
        self.assertEqual(
            set(RENDERERS),
            {
                "game_dialogues",
                "game_quests",
                "game_updates",
                "game_announcements",
                "kim_dialogues",
                "lore_items",
                "warframes",
            },
        )


if __name__ == "__main__":
    unittest.main()
