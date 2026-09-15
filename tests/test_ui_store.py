"""LoreStore (UI) — rechargement incrémental et recherche.

Vérifie que le store ne re-parse que les megafiles réellement changés
(empreinte mtime/taille) et que la recherche conserve sa hiérarchie
titre > contenu — y compris après rechargement.
"""

from __future__ import annotations

from warframe_lore.ui.data.store import LoreStore


def _reset_interval(store: LoreStore, elapsed: float = 60.0) -> None:
    """Place la dernière relecture dans le passé pour forcer ``maybe_reload``."""
    store._last_reload -= elapsed


def test_charge_les_megafiles(megafiles):
    store = LoreStore(megafiles)
    assert store.stats()["pages"] == 3
    assert store.stats()["buckets"] == 2
    assert sorted(store.list_buckets()[0])  # dict de bucket bien formé


def test_recherche_priorite_aux_titres(megafiles):
    store = LoreStore(megafiles)
    hits = store.search("hildryn")
    assert hits and hits[0]["page_title"] == "Hildryn"
    assert hits[0]["match_type"] == "title"
    assert hits[0]["bucket_id"] == "Premier"


def test_recherche_contenu_et_canon(megafiles):
    store = LoreStore(megafiles)
    hits = store.search("spartiate")
    assert hits[0]["match_type"] == "content"
    assert hits[0]["page_title"] == "Styanax"
    # Filtré hors canon -> plus aucun résultat de contenu pour ce bucket
    hits = store.search("ennemi", canon="canon")
    assert hits == []


def test_suggest_insensible_a_la_casse(megafiles):
    store = LoreStore(megafiles)
    laps = store.suggest("HIL")
    assert laps and laps[0]["page_title"] == "Hildryn"
    assert laps[0]["match_type"] == "title"


def test_reload_sans_changement_ne_reparse_pas(megafiles):
    store = LoreStore(megafiles)
    empreinte = dict(store._file_state)
    store.reload()
    assert store._file_state == empreinte


def test_reload_detecte_un_nouveau_bucket(megafiles, megafile_writer):
    store = LoreStore(megafiles)
    megafile_writer(
        megafiles, "Tiers",
        [{"page_title": "Nova", "content_markdown": "La porteuse d'antimatière.",
          "canon_status": "canon", "last_updated": "2024-01-04"}],
        mtime=10)
    _reset_interval(store)
    store.maybe_reload()
    assert store.bucket_exists("Tiers")
    assert store.stats()["pages"] == 4
    assert store.search("porteuse")[0]["match_type"] == "content"


def test_reload_retire_un_bucket_supprime(megafiles, megafile_writer):
    store = LoreStore(megafiles)
    target = megafiles / "Second.json"
    assert target.exists()
    target.unlink()
    _reset_interval(store)
    store.maybe_reload()
    assert not store.bucket_exists("Second")
    assert store.stats()["pages"] == 2


def test_reload_voit_la_modification_d_un_megafile(megafiles, megafile_writer):
    store = LoreStore(megafiles)
    megafile_writer(
        megafiles, "Premier",
        [{"page_title": "Hildryn",
          "content_markdown": "Gardienne, à présent accompagnée de l'Ordos.",
          "canon_status": "canon", "last_updated": "2024-01-05"}],
        metadata={"bucket_title": "Études", "generated_at": "2024-01-05"},
        mtime=20)
    _reset_interval(store)
    store.maybe_reload()
    assert store.search("ordos")[0]["match_type"] == "content"
    # La page Styanax a disparu du megafile -> son index suit
    assert store.search("spartiate") == []


def test_recent_et_compteurs_utilisent_les_index(megafiles):
    store = LoreStore(megafiles)
    assert store.recent(limit=1)[0]["page_title"] == "Hildryn"
    buckets = {b["id"]: b for b in store.list_buckets()}
    assert buckets["Premier"]["canon"] == 1
    assert buckets["Premier"]["speculation"] == 1
    assert buckets["Second"]["canon"] == 1
    assert store.page_titles_by_bucket()["Premier"] == ["Hildryn", "Styanax"]
