"""Generic domain models for declarative GitHub/JSON collection and enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class GithubDirectoryConfig:
    """Configuration for a github_directory discovery source."""

    repo: str
    path: str = ""
    ref: str = "main"
    pattern: str = "*.json"
    mirror_url_template: str | None = None
    token_env: str = "GITHUB_TOKEN"
    api_base_url: str = "https://api.github.com"


@dataclass(frozen=True, slots=True)
class CollectionFilterConfig:
    """Generic filtering rules for JSON document collections."""

    min_items: int = 0
    max_items: int | None = None
    required_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DictLookupRuleConfig:
    """Generic external dictionary lookup and field-injection configuration."""

    source_field: str
    target_field: str = "resolved"
    prefix: str | None = None
    regex: str | None = None
    dictionaries: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class JsonCollectionPreset:
    """Complete declarative preset for a JSON collection & enrichment pipeline."""

    name: str
    discovery: GithubDirectoryConfig
    filter_rule: CollectionFilterConfig = field(
        default_factory=CollectionFilterConfig
    )
    dict_lookup: DictLookupRuleConfig | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DiscoveredResource:
    """One file entry discovered from a remote directory listing."""

    name: str
    path: str
    sha: str
    download_url: str
    mirror_url: str | None = None

    def primary_url(self) -> str:
        return self.mirror_url or self.download_url

    def fallback_url(self) -> str | None:
        has_alt = bool(self.mirror_url and self.download_url)
        if has_alt and self.mirror_url != self.download_url:
            return self.download_url
        return None


@dataclass(slots=True)
class ManifestEntry:
    """Version metadata persisted per remote resource or dictionary."""

    sha: str = ""
    etag: str = ""
    last_modified: str = ""
    cached_payload: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "sha": self.sha,
            "etag": self.etag,
            "last_modified": self.last_modified,
        }
        if self.cached_payload is not None:
            out["cached_payload"] = self.cached_payload
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ManifestEntry:
        return cls(
            sha=str(raw.get("sha") or ""),
            etag=str(raw.get("etag") or ""),
            last_modified=str(raw.get("last_modified") or ""),
            cached_payload=raw.get("cached_payload"),
        )


@dataclass(slots=True)
class CollectedJsonDocument:
    """One collected, filtered and enriched JSON document."""

    name: str
    source_url: str
    sha: str
    data: Any
    resolved_count: int = 0
    missing_keys: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CollectionRunResult:
    """Summary of a generic JSON collection run."""

    documents: list[CollectedJsonDocument] = field(default_factory=list)
    skipped_unchanged: list[str] = field(default_factory=list)
    filtered_out: list[str] = field(default_factory=list)
    missing_keys: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
