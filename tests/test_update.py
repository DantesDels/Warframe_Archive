"""Unit tests for the ``update`` package: merge rules and rendering.

Pure-function tests (no database, no network): ``kim_subjects_from_contexts``,
``leverian_frames_from_chunks``, ``merge_sources`` and ``render_story_eras``.
"""

from __future__ import annotations

import unittest

from warframe_lore.update.merge import (
    ERA_1999,
    ERA_EVEIL,
    kim_subjects_from_contexts,
    leverian_frames_from_chunks,
    merge_sources,
    render_story_eras,
)


class KimSubjectsTests(unittest.TestCase):
    def test_amir_et_minerva_extraits(self):
        contexts = ["KIM \ufffd Amir", "KIM \ufffd Minerva, Velimir"]
        subjects = kim_subjects_from_contexts(contexts)
        self.assertIn("amir", subjects)
        self.assertIn("minerva", subjects)
        self.assertIn("velimir", subjects)

    def test_fables_exclu(self):
        subjects = kim_subjects_from_contexts(["KIM \ufffd Fables & Frontiers"])
        self.assertEqual(subjects, set())

    def test_contexte_vide_ou_non_kim(self):
        self.assertEqual(kim_subjects_from_contexts(["", "Perrin Sequence"]), set())

    def test_contexte_kim_brise(self):
        subjects = kim_subjects_from_contexts(["KIM \ufffd"])
        self.assertEqual(subjects, set())


class LeverianFramesTests(unittest.TestCase):
    def test_intersection_sections_et_frames(self):
        chunks = ["Section: Excalibur", "Section: Mag", "Section: Lokus"]
        base_frames = ["Excalibur", "Mag", "Rhino"]
        result = leverian_frames_from_chunks(chunks, base_frames)
        self.assertEqual(result, frozenset({"excalibur", "mag"}))

    def test_page_absente_renvoie_vide(self):
        result = leverian_frames_from_chunks([], ["Excalibur"])
        self.assertEqual(result, frozenset())

    def test_sections_hors_dossier_ignorées(self):
        chunks = ["Section: Ordis"]
        result = leverian_frames_from_chunks(chunks, ["Excalibur"])
        self.assertEqual(result, frozenset())


class MergeSourcesTests(unittest.TestCase):
    def test_kim_sujet_ajouté_en_1999(self):
        mapping, _ = merge_sources(
            {}, frozenset(), kim_subjects={"amir"})
        self.assertEqual(mapping.get("amir"), ERA_1999)

    def test_warframe_ajouté_en_eveil(self):
        mapping, _ = merge_sources(
            {}, frozenset(), frames=["Grendel"])
        self.assertEqual(mapping.get("grendel"), ERA_EVEIL)

    def test_quest_titre_mappé_via_quest_eras(self):
        mapping, _ = merge_sources(
            {}, frozenset(), quest_titles=["The Hex"])
        self.assertEqual(mapping.get("the hex"), ERA_1999)

    def test_quest_titre_inconnu_non_ajouté(self):
        mapping, _ = merge_sources(
            {}, frozenset(), quest_titles=["Random Quest"])
        self.assertNotIn("random quest", mapping)

    def test_setdefault_ne_surcharge_pas(self):
        curated = {"amir": "custom-era"}
        mapping, _ = merge_sources(
            curated, frozenset(), kim_subjects={"amir"})
        self.assertEqual(mapping.get("amir"), "custom-era")

    def test_leverian_frames_prioritaire(self):
        _, leverian = merge_sources(
            {}, frozenset({"old"}),
            leverian_frames=frozenset({"excalibur", "mag"}))
        self.assertEqual(leverian, frozenset({"excalibur", "mag"}))

    def test_ambiguous_exclu(self):
        mapping, _ = merge_sources(
            {}, frozenset(), frames=["Grendel"],
            ambiguous=frozenset({"grendel"}))
        self.assertNotIn("grendel", mapping)

    def test_frames_ambigus_du_curaté_exclus(self):
        # Garuda est le seul sujet ambigu du curaté (story.STORY_SUBJECT_CHOICES):
        # la régénération (lists.regenerate_story_eras) l'exclut des frames.
        from warframe_lore.discord.guild.story import STORY_SUBJECT_CHOICES

        mapping, _ = merge_sources(
            {}, frozenset(), frames=["Garuda", "Gauss"],
            ambiguous=frozenset(STORY_SUBJECT_CHOICES))
        self.assertNotIn("garuda", mapping)
        self.assertEqual(mapping.get("gauss"), ERA_EVEIL)


class RenderStoryErasTests(unittest.TestCase):
    def test_format_contient_header_et_footer(self):
        rendered = render_story_eras({}, frozenset())
        self.assertIn('"""Canonical era mapping', rendered)
        self.assertIn("LEVERIAN_WARFRAMES: frozenset[", rendered)

    def test_groupes_par_era(self):
        mapping = {"amir": ERA_1999, "eleanor": ERA_1999}
        rendered = render_story_eras(mapping, frozenset())
        self.assertIn("# 1999 (Höllvania)", rendered)
        self.assertIn('"amir"', rendered)
        self.assertIn('"eleanor"', rendered)

    def test_cles_triees_alphabetiquement(self):
        mapping = {"zframe": ERA_EVEIL, "aframe": ERA_EVEIL}
        rendered = render_story_eras(mapping, frozenset())
        pos_a = rendered.index('"aframe"')
        pos_z = rendered.index('"zframe"')
        self.assertLess(pos_a, pos_z)

    def test_leverian_trie(self):
        rendered = render_story_eras({}, frozenset({"Mag", "Excalibur"}))
        self.assertIn('"Excalibur"', rendered)
        self.assertIn('"Mag"', rendered)
        pos_e = rendered.index('"Excalibur"')
        pos_m = rendered.index('"Mag"')
        self.assertLess(pos_e, pos_m)

    def test_era_inconnue_appepend(self):
        mapping = {"x": "custom-era"}
        rendered = render_story_eras(mapping, frozenset())
        self.assertIn('"x": "custom-era"', rendered)
        self.assertNotIn("# custom-era", rendered)


if __name__ == "__main__":
    unittest.main()
