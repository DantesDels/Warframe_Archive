"""Pure request/response helpers for the httpx GitHub & JSON adapter."""

from __future__ import annotations

import fnmatch
import os
from typing import Any

from .models import DiscoveredResource, GithubDirectoryConfig


def build_github_contents_request(
    config: GithubDirectoryConfig,
) -> tuple[str, dict[str, str]]:
    """Build the GitHub contents API URL and request headers."""
    clean_path = config.path.strip("/")
    api_base = config.api_base_url.rstrip("/")
    url = f"{api_base}/repos/{config.repo}/contents/{clean_path}"
    if config.ref:
        url = f"{url}?ref={config.ref}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get(config.token_env, "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return url, headers


def parse_github_directory_entries(
    payload: Any, config: GithubDirectoryConfig
) -> list[DiscoveredResource]:
    """Filter GitHub directory entries by pattern and format mirror URLs."""
    entries = payload if isinstance(payload, list) else [payload]
    found: list[DiscoveredResource] = []
    for item in entries:
        if not isinstance(item, dict) or item.get("type") not in (None, "file"):
            continue
        name = str(item.get("name") or "")
        if not name or not fnmatch.fnmatch(name, config.pattern):
            continue
        rel_path = str(item.get("path") or name)
        sha = str(item.get("sha") or "")
        dl_url = str(item.get("download_url") or "")
        mirror_url: str | None = None
        if config.mirror_url_template:
            mirror_url = config.mirror_url_template.format(
                filename=name,
                name=name,
                path=rel_path,
                repo=config.repo,
                ref=config.ref,
            )
        found.append(
            DiscoveredResource(
                name=name,
                path=rel_path,
                sha=sha,
                download_url=dl_url,
                mirror_url=mirror_url,
            )
        )
    return found


def extract_flat_dict(raw: Any) -> dict[str, str]:
    """Flatten a JSON dictionary response into a string-to-string lookup map."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw.items():
        if isinstance(v, (str, int, float, bool)):
            out[str(k)] = str(v)
        elif isinstance(v, dict):
            for sk, sv in v.items():
                if isinstance(sv, (str, int, float, bool)):
                    out[str(sk)] = str(sv)
    return out


def response_etag_and_modified(headers: Any) -> tuple[str, str]:
    """Extract ETag and Last-Modified headers case-insensitively."""
    etag = str(headers.get("ETag") or headers.get("etag") or "")
    mod = str(headers.get("Last-Modified") or headers.get("last-modified") or "")
    return etag, mod
