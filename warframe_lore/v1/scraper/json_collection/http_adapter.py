"""Outbound HTTP & GitHub directory adapter built on httpx with mirror fallback."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .http_helpers import (
    build_github_contents_request,
    extract_flat_dict,
    parse_github_directory_entries,
    response_etag_and_modified,
)
from .manifest import ManifestStore
from .models import DiscoveredResource, GithubDirectoryConfig


class HttpxJsonAdapter:
    """Generic httpx client adapter for GitHub directory discovery and JSON fetch."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        timeout: float = 20.0,
        max_retries: int = 2,
        backoff: float = 0.2,
    ) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=True)
        self.max_retries = max(0, int(max_retries))
        self.backoff = float(backoff)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _get_with_retries(
        self, url: str, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.get(url, headers=headers)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(self.backoff * (attempt + 1))
                    continue
                return resp
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff * (attempt + 1))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"HTTP request failed for {url}")

    def discover_github_directory(
        self, config: GithubDirectoryConfig
    ) -> list[DiscoveredResource]:
        """List files in a GitHub directory via the contents API with pattern match."""
        url, headers = build_github_contents_request(config)
        resp = self._get_with_retries(url, headers=headers)
        resp.raise_for_status()
        return parse_github_directory_entries(resp.json(), config)

    def fetch_resource_json(
        self,
        resource: DiscoveredResource,
        manifest: ManifestStore,
        *,
        force: bool = False,
    ) -> tuple[Any, bool, str]:
        """Fetch one JSON resource via mirror (with download_url fallback) and ETag."""
        key = f"resource:{resource.path}"
        if manifest.is_unchanged(key, sha=resource.sha, force=force):
            return None, True, resource.primary_url()
        cond_headers = manifest.conditional_headers(key, force=force)
        urls = [u for u in (resource.primary_url(), resource.fallback_url()) if u]
        last_err: Exception | None = None
        for idx, target_url in enumerate(urls):
            hdrs = cond_headers if idx == 0 else {}
            try:
                resp = self._get_with_retries(target_url, headers=hdrs)
                if resp.status_code == 304 and not force:
                    manifest.update(key, sha=resource.sha)
                    return None, True, target_url
                resp.raise_for_status()
                data = resp.json()
                etag, mod = response_etag_and_modified(resp.headers)
                manifest.update(key, sha=resource.sha, etag=etag, last_modified=mod)
                return data, False, target_url
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        if last_err is not None:
            raise last_err
        raise RuntimeError(f"No download URL available for {resource.name}")

    def fetch_dictionary(
        self,
        lang: str,
        url: str,
        manifest: ManifestStore,
        *,
        force: bool = False,
    ) -> dict[str, str]:
        """Fetch an external key/value JSON dictionary with ETag manifest caching."""
        key = f"dict:{lang}:{url}"
        entry = manifest.get(key)
        has_cached = entry is not None and isinstance(entry.cached_payload, dict)
        headers = manifest.conditional_headers(key, force=force or not has_cached)
        resp = self._get_with_retries(url, headers=headers)
        if resp.status_code == 304 and has_cached and entry is not None:
            return {str(k): str(v) for k, v in entry.cached_payload.items()}
        resp.raise_for_status()
        payload = extract_flat_dict(resp.json())
        etag, mod = response_etag_and_modified(resp.headers)
        manifest.update(key, etag=etag, last_modified=mod, cached_payload=payload)
        return payload
