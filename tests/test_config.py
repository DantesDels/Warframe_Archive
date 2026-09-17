"""Configuration du scraper — valeurs par défaut et surcharges env.

Verrouille l'API publique de ``Config`` : les champs morts supprimés lors du
refactor (``state_file``, ``buckets``) ne doivent jamais réapparaître, et
``load_config()`` applique bien les variables ``WF_*`` (l'env par-dessus le
fichier ``.env``, jamais l'inverse).
"""

from __future__ import annotations

import os

from warframe_lore.config import Config, load_config
from warframe_lore.discord.config import (
    DiscordConfig,
    load_channels_file,
)
from warframe_lore.envfile import load_dotenv


def test_config_par_defaut_sans_champs_morts():
    cfg = Config()
    assert isinstance(cfg.api_url, str) and cfg.api_url.startswith("https://")
    assert not hasattr(cfg, "state_file")
    assert not hasattr(cfg, "buckets")
    assert cfg.output_format == "json"


def test_load_config_applique_les_surcharges_env(monkeypatch):
    monkeypatch.setenv("WF_MAX_RETRIES", "12")
    monkeypatch.setenv("WF_TIMEOUT", "3.5")
    monkeypatch.setenv("WF_SLEEP", "0.2")
    monkeypatch.setenv("WF_OUTPUT_DIR", r"C:\tmp\warframe_out")
    monkeypatch.setenv("WF_DATABASE_URL",
                       "postgresql+asyncpg://x:y@localhost:5432/z")
    cfg = load_config()
    assert cfg.max_retries == 12
    assert cfg.request_timeout == 3.5
    assert cfg.min_sleep_between_requests == 0.2
    assert str(cfg.output_dir) == r"C:\tmp\warframe_out"
    assert "//x:y@" in cfg.database_url


def test_load_config_sans_env_retombe_sur_les_defauts(monkeypatch):
    for var in ("WF_MAX_RETRIES", "WF_TIMEOUT", "WF_SLEEP",
                "WF_OUTPUT_DIR", "WF_DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)
    defaults = Config()
    cfg = load_config()
    assert cfg.max_retries == defaults.max_retries
    assert cfg.request_timeout == defaults.request_timeout


def test_env_toujours_prioritaire_sur_le_fichier_env(monkeypatch, tmp_path):
    env = tmp_path / "env_vars"
    env.write_text("WF_MAX_RETRIES=2\nWF_TIMEOUT=9\n", encoding="utf-8")
    # l'env existant doit GAGNER face au fichier : la valeur setenv wins.
    monkeypatch.setenv("WF_MAX_RETRIES", "7")
    load_dotenv(env)
    assert os.environ["WF_MAX_RETRIES"] == "7"
    # en revanche, une clef absente de l'env est bien chargée depuis le fichier.
    monkeypatch.delenv("WF_TIMEOUT", raising=False)
    load_dotenv(env)
    assert os.environ["WF_TIMEOUT"] == "9"


# ------------------------------------------------------------------
# Fichier de config des canaux (ID et/ou nom)
# ------------------------------------------------------------------

def test_load_channels_file_id(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"channel_id": 1550171060295442482}', encoding="utf-8")
    ids, names = load_channels_file(p)
    assert ids == {1550171060295442482}
    assert names == set()


def test_load_channels_file_name(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"channel_name": "〉ᴏʀᴀᴄʟᴇ"}', encoding="utf-8")
    ids, names = load_channels_file(p)
    assert ids == set()
    assert names == {"〉ᴏʀᴀᴄʟᴇ"}


def test_load_channels_file_absent(tmp_path):
    ids, names = load_channels_file(tmp_path / "absent.json")
    assert ids == set() and names == set()


def test_config_fusionne_env_et_fichier_canaux(monkeypatch, tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"channel_id": 1550171060295442482, '
                 '"channel_name": "〉ᴏʀᴀᴄʟᴇ"}', encoding="utf-8")
    monkeypatch.setenv("DISCORD_CHANNELS_FILE", str(p))
    monkeypatch.setenv("DISCORD_CHANNELS", "11")
    config = DiscordConfig.load()
    assert 11 in config.allowed_channels
    assert 1550171060295442482 in config.allowed_channels
    assert config.allowed_channel_names == ("〉ᴏʀᴀᴄʟᴇ",)


def test_config_fichier_absent_retombe_sur_env(monkeypatch):
    monkeypatch.setenv("DISCORD_CHANNELS", "77")
    monkeypatch.setenv("DISCORD_CHANNEL_NAMES", "oracle")
    monkeypatch.setenv("DISCORD_CHANNELS_FILE", "/nonexistent/file.json")
    config = DiscordConfig.load()
    assert config.allowed_channels == (77,)
    assert config.allowed_channel_names == ("oracle",)
