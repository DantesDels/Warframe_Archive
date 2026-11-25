"""Unit and preset integration tests for generic GitHub/JSON collection & lookup."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx
import pytest

from warframe_lore.v1.scraper.adapters.outbound.connectors.registry import (
    default_registry,
)
from warframe_lore.v1.scraper.json_collection import (
    CollectionFilterConfig,
    DictLookupRuleConfig,
    GithubDirectoryConfig,
    HttpxJsonAdapter,
    JsonCollectionPreset,
    JsonCollectionService,
    ManifestStore,
    load_preset,
)
from warframe_lore.v1.scraper.json_collection.cli import build_parser
from warframe_lore.v1.scraper.ports.outbound.sources import ConnectorContext


def test_generic_github_discovery_mirror_fallback_and_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen_headers: list[dict[str, str]] = []
    requested_urls: list[str] = []

    monkeypatch.setenv("CUSTOM_GH_TOKEN", "ghp_test_token_123")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested_urls.append(url)
        seen_headers.append(dict(request.headers))
        if "api.github.com/repos/acme/ narratives/contents/dialogs".replace(
            " ", ""
        ) in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "chapter1.scene.json",
                        "path": "dialogs/chapter1.scene.json",
                        "type": "file",
                        "sha": "sha-ch1",
                        "download_url": "https://raw.example.test/dialogs/chapter1.scene.json",
                    },
                    {
                        "name": "chapter2.scene.json",
                        "path": "dialogs/chapter2.scene.json",
                        "type": "file",
                        "sha": "sha-ch2",
                        "download_url": "https://raw.example.test/dialogs/chapter2.scene.json",
                    },
                    {
                        "name": "readme.md",
                        "path": "dialogs/readme.md",
                        "type": "file",
                        "sha": "sha-doc",
                        "download_url": "https://raw.example.test/dialogs/readme.md",
                    },
                ],
            )
        if url == "https://mirror.example.test/files/chapter1.scene.json":
            return httpx.Response(
                200,
                headers={"ETag": '"etag-ch1"'},
                json=[{"id": i, "line": f"msg-{i}"} for i in range(6)],
            )
        if url == "https://mirror.example.test/files/chapter2.scene.json":
            # Simulate mirror failure -> must fall back to GitHub download_url
            return httpx.Response(502, text="Bad Gateway")
        if url == "https://raw.example.test/dialogs/chapter2.scene.json":
            return httpx.Response(
                200,
                headers={"ETag": '"etag-ch2"'},
                json=[{"id": i, "line": f"fallback-{i}"} for i in range(5)],
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpxJsonAdapter(client=client, max_retries=0)
    cfg = GithubDirectoryConfig(
        repo="acme/narratives",
        path="dialogs",
        ref="v2",
        pattern="*.scene.json",
        mirror_url_template="https://mirror.example.test/files/{filename}",
        token_env="CUSTOM_GH_TOKEN",
    )
    resources = adapter.discover_github_directory(cfg)
    assert [r.name for r in resources] == [
        "chapter1.scene.json",
        "chapter2.scene.json",
    ]
    assert seen_headers[0]["authorization"] == "Bearer ghp_test_token_123"

    manifest = ManifestStore(tmp_path / "manifest.json")
    data1, unchanged1, url1 = adapter.fetch_resource_json(resources[0], manifest)
    assert unchanged1 is False
    assert url1 == "https://mirror.example.test/files/chapter1.scene.json"
    assert len(data1) == 6

    data2, unchanged2, url2 = adapter.fetch_resource_json(resources[1], manifest)
    assert unchanged2 is False
    assert url2 == "https://raw.example.test/dialogs/chapter2.scene.json"
    assert len(data2) == 5


def test_generic_incremental_manifest_sync_and_force_flag(tmp_path: Path) -> None:
    fetch_counts = {"file": 0, "dict_en": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com/repos/org/repo/contents/items" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "valid.data.json",
                        "path": "items/valid.data.json",
                        "type": "file",
                        "sha": "sha-v1",
                        "download_url": "https://cdn.example.test/valid.data.json",
                    }
                ],
            )
        if url == "https://cdn.example.test/dict.en.json":
            if request.headers.get("if-none-match") == '"dict-etag-1"':
                return httpx.Response(304)
            fetch_counts["dict_en"] += 1
            return httpx.Response(
                200,
                headers={"ETag": '"dict-etag-1"'},
                json={"/App/Strings/Greeting": "Hello Traveler"},
            )
        if url == "https://cdn.example.test/valid.data.json":
            fetch_counts["file"] += 1
            return httpx.Response(
                200,
                headers={"ETag": '"file-etag-1"', "Last-Modified": "Wed, 21 Oct 2026"},
                json=[
                    {"node": i, "text_key": "/App/Strings/Greeting"} for i in range(5)
                ],
            )
        return httpx.Response(404)

    preset = JsonCollectionPreset(
        name="generic_sync_test",
        discovery=GithubDirectoryConfig(
            repo="org/repo",
            path="items",
            ref="main",
            pattern="*.data.json",
        ),
        filter_rule=CollectionFilterConfig(min_items=5),
        dict_lookup=DictLookupRuleConfig(
            source_field="text_key",
            target_field="resolved",
            prefix="/App/Strings/",
            dictionaries={"en": "https://cdn.example.test/dict.en.json"},
        ),
    )
    manifest_path = tmp_path / "sync_manifest.json"
    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpxJsonAdapter(client=client, max_retries=0)

    # First run downloads both the dictionary and the file
    service1 = JsonCollectionService(
        adapter=adapter, manifest=ManifestStore(manifest_path)
    )
    res1 = service1.run(preset, force=False)
    assert len(res1.documents) == 1
    assert res1.skipped_unchanged == []
    assert fetch_counts == {"file": 1, "dict_en": 1}
    assert manifest_path.is_file()

    # Second run reloads manifest from disk: dictionary gets 304 (cached),
    # file is skipped via matching SHA without downloading
    service2 = JsonCollectionService(
        adapter=adapter, manifest=ManifestStore(manifest_path)
    )
    res2 = service2.run(preset, force=False)
    assert res2.documents == []
    assert res2.skipped_unchanged == ["valid.data.json"]
    assert fetch_counts == {"file": 1, "dict_en": 1}

    # Third run with force=True (--force) re-downloads and reprocesses everything
    parser = build_parser()
    parsed = parser.parse_args(["--preset", "demo.yaml", "--force"])
    assert parsed.force is True
    res3 = service2.run(preset, force=True)
    assert len(res3.documents) == 1
    assert fetch_counts == {"file": 2, "dict_en": 2}


def test_generic_min_items_filter_and_multilang_dict_lookup_with_missing_keys(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "api.github.com/repos/studio/game/contents/scripts" in url:
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "empty_shell.script.json",
                        "path": "scripts/empty_shell.script.json",
                        "type": "file",
                        "sha": "sha-empty",
                        "download_url": "https://cdn.example.test/empty_shell.script.json",
                    },
                    {
                        "name": "main_quest.script.json",
                        "path": "scripts/main_quest.script.json",
                        "type": "file",
                        "sha": "sha-main",
                        "download_url": "https://cdn.example.test/main_quest.script.json",
                    },
                ],
            )
        if url == "https://cdn.example.test/empty_shell.script.json":
            return httpx.Response(
                200,
                json=[{"id": 1, "Label": "/I18n/Key/One"}, {"id": 2, "Label": "Raw"}],
            )
        if url == "https://cdn.example.test/main_quest.script.json":
            return httpx.Response(
                200,
                json=[
                    {"id": 1, "Label": "/I18n/Key/One", "extra": "keep-me"},
                    {"id": 2, "Label": "/I18n/Key/Missing"},
                    {"id": 3, "Label": "Plain literal text"},
                    {"id": 4, "nested": {"Label": "/I18n/Key/Two"}},
                    {"id": 5, "Label": "/I18n/Key/One"},
                ],
            )
        if url == "https://cdn.example.test/i18n.en.json":
            return httpx.Response(
                200,
                json={
                    "/I18n/Key/One": "First Line",
                    "/I18n/Key/Two": "Second Line",
                },
            )
        if url == "https://cdn.example.test/i18n.fr.json":
            return httpx.Response(
                200,
                json={
                    "/I18n/Key/One": "Première ligne",
                    "/I18n/Key/Two": "Deuxième ligne",
                },
            )
        return httpx.Response(404)

    preset = JsonCollectionPreset(
        name="generic_lookup_test",
        discovery=GithubDirectoryConfig(
            repo="studio/game",
            path="scripts",
            ref="dev",
            pattern="*.script.json",
        ),
        filter_rule=CollectionFilterConfig(min_items=5),
        dict_lookup=DictLookupRuleConfig(
            source_field="Label",
            target_field="resolved",
            prefix="/I18n/Key/",
            dictionaries={
                "en": "https://cdn.example.test/i18n.en.json",
                "fr": "https://cdn.example.test/i18n.fr.json",
            },
        ),
    )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpxJsonAdapter(client=client, max_retries=0)
    service = JsonCollectionService(
        adapter=adapter, manifest=ManifestStore(tmp_path / "m.json")
    )

    with caplog.at_level(logging.WARNING):
        result = service.run(preset)

    # empty_shell.script.json has 2 items (< 5) -> filtered out
    assert result.filtered_out == ["empty_shell.script.json"]
    assert len(result.documents) == 1

    doc = result.documents[0]
    assert doc.name == "main_quest.script.json"
    items: list[dict[str, Any]] = doc.data
    assert len(items) == 5

    # Original structure and source_field are preserved intact
    assert items[0]["Label"] == "/I18n/Key/One"
    assert items[0]["extra"] == "keep-me"
    assert items[0]["resolved"] == {
        "en": "First Line",
        "fr": "Première ligne",
    }

    # Missing key does not crash: sets None, records missing key, logs warning
    assert items[1]["Label"] == "/I18n/Key/Missing"
    assert items[1]["resolved"] == {"en": None, "fr": None}
    assert "en:/I18n/Key/Missing" in doc.missing_keys
    assert "fr:/I18n/Key/Missing" in doc.missing_keys
    assert any("Missing dictionary key" in rec.message for rec in caplog.records)

    # Non-matching literal string is untouched
    assert items[2]["Label"] == "Plain literal text"
    assert "resolved" not in items[2]

    # Nested object is also enriched recursively
    assert items[3]["nested"]["Label"] == "/I18n/Key/Two"
    assert items[3]["nested"]["resolved"] == {
        "en": "Second Line",
        "fr": "Deuxième ligne",
    }


def test_warframe_kim_declarative_preset_loading_and_end_to_end_execution(
    tmp_path: Path,
) -> None:
    # Load via both relative 'configs/warframe_kim.yaml' and full v1 path
    preset = load_preset("configs/warframe_kim.yaml")
    assert preset.discovery.repo == "Sainan/warframe-kim-dialogues"
    assert preset.discovery.path == "data"
    assert preset.discovery.ref == "senpai"
    assert preset.discovery.pattern == "*.dialogue.json"
    assert (
        preset.discovery.mirror_url_template
        == "https://kim.browse.wf/data/{filename}"
    )
    assert preset.filter_rule.min_items == 5
    assert preset.dict_lookup is not None
    assert preset.dict_lookup.source_field == "Content"
    assert preset.dict_lookup.target_field == "resolved"
    assert preset.dict_lookup.prefix == "/Lotus/Language/"
    assert preset.dict_lookup.dictionaries == {
        "en": "https://browse.wf/warframe-public-export-plus/dict.en.json",
        "fr": "https://browse.wf/warframe-public-export-plus/dict.fr.json",
    }

    # Also verify ConnectorRegistry resolves github_directory sources
    reg = default_registry()
    ctx = ConnectorContext(client=None, limits={})
    conn = reg.resolve(
        {"kind": "github_directory", "location": "configs/warframe_kim.yaml"},
        ctx,
    )
    assert conn.name == "github_directory"

    # End-to-end execution of the loaded preset with mocked HTTP responses
    tag_1 = "/Lotus/Language/1999Dialogue/ArthurGreeting01"
    tag_2 = "/Lotus/Language/1999Dialogue/ArthurReply02"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if (
            url
            == "https://api.github.com/repos/Sainan/warframe-kim-dialogues/contents/data?ref=senpai"
        ):
            return httpx.Response(
                200,
                json=[
                    {
                        "name": "MinervaDialogue_rom.dialogue.json",
                        "path": "data/MinervaDialogue_rom.dialogue.json",
                        "type": "file",
                        "sha": "sha-minerva",
                        "download_url": "https://raw.githubusercontent.com/Sainan/warframe-kim-dialogues/senpai/data/MinervaDialogue_rom.dialogue.json",
                    },
                    {
                        "name": "VelimirDialogue_rom.dialogue.json",
                        "path": "data/VelimirDialogue_rom.dialogue.json",
                        "type": "file",
                        "sha": "sha-velimir",
                        "download_url": "https://raw.githubusercontent.com/Sainan/warframe-kim-dialogues/senpai/data/VelimirDialogue_rom.dialogue.json",
                    },
                    {
                        "name": "ArthurDialogue_rom.dialogue.json",
                        "path": "data/ArthurDialogue_rom.dialogue.json",
                        "type": "file",
                        "sha": "sha-arthur",
                        "download_url": "https://raw.githubusercontent.com/Sainan/warframe-kim-dialogues/senpai/data/ArthurDialogue_rom.dialogue.json",
                    },
                ],
            )
        if url == "https://kim.browse.wf/data/MinervaDialogue_rom.dialogue.json":
            return httpx.Response(200, json=[{"Id": 1}])
        if url == "https://kim.browse.wf/data/VelimirDialogue_rom.dialogue.json":
            return httpx.Response(200, json=[{"Id": 1}, {"Id": 2}])
        if url == "https://kim.browse.wf/data/ArthurDialogue_rom.dialogue.json":
            return httpx.Response(
                200,
                json=[
                    {"Id": 1, "Content": tag_1},
                    {"Id": 2, "Content": tag_2},
                    {"Id": 3, "Content": "CheckRank"},
                    {"Id": 4, "Content": tag_1},
                    {"Id": 5, "Content": tag_2},
                ],
            )
        if url == "https://browse.wf/warframe-public-export-plus/dict.en.json":
            return httpx.Response(
                200,
                json={
                    tag_1: "Hey there, Drifter.",
                    tag_2: "Stay sharp out there.",
                },
            )
        if url == "https://browse.wf/warframe-public-export-plus/dict.fr.json":
            return httpx.Response(
                200,
                json={
                    tag_1: "Salut, Voyageur.",
                    tag_2: "Reste sur tes gardes.",
                },
            )
        return httpx.Response(404, text=json.dumps({"url": url}))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = HttpxJsonAdapter(client=client, max_retries=0)
    service = JsonCollectionService(
        adapter=adapter, manifest=ManifestStore(tmp_path / "kim_manifest.json")
    )
    res = service.run(preset)

    assert set(res.filtered_out) == {
        "MinervaDialogue_rom.dialogue.json",
        "VelimirDialogue_rom.dialogue.json",
    }
    assert len(res.documents) == 1
    arthur = res.documents[0]
    assert arthur.name == "ArthurDialogue_rom.dialogue.json"
    assert arthur.source_url == "https://kim.browse.wf/data/ArthurDialogue_rom.dialogue.json"
    assert arthur.data[0]["Content"] == tag_1
    assert arthur.data[0]["resolved"] == {
        "en": "Hey there, Drifter.",
        "fr": "Salut, Voyageur.",
    }
    assert arthur.data[1]["resolved"] == {
        "en": "Stay sharp out there.",
        "fr": "Reste sur tes gardes.",
    }
    assert "resolved" not in arthur.data[2]
