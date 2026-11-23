"""Optional Playwright connector for JS/SPA pages."""

from __future__ import annotations

from typing import Any

from ....ports.outbound.sources import CollectedPage, ConnectorContext


class PlaywrightConnector:
    name = "playwright"
    kinds = ("website", "spa")

    def can_handle(self, source: dict[str, Any], ctx: ConnectorContext) -> bool:
        if not bool(ctx.limits.get("use_playwright", False)):
            return False
        kind = str(source.get("kind", "")).lower()
        return kind in {"spa", "website"}

    def collect(
        self, source: dict[str, Any], ctx: ConnectorContext
    ) -> list[CollectedPage]:
        url = str(source.get("location", "")).strip()
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("Playwright non installé/configuré") from exc
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            title = page.title() or url
            content = page.inner_text("body")
            browser.close()
        return [
            CollectedPage(
                title=title, url=url, content=content, raw=content.encode("utf-8")
            )
        ]
