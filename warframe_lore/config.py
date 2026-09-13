"""Central configuration for the Warframe lore scraper."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .envfile import load_dotenv

# Project root is the parent of the package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    """Runtime configuration for the scraper.

    All values can be overridden via CLI flags or environment variables.
    """

    # --- MediaWiki API ---
    api_url: str = "https://wiki.warframe.com/api.php"
    source_url_base: str = "https://wiki.warframe.com/wiki/"
    user_agent: str = "WarframeLoreScraper/1.0 (data engineering; contact: local)"

    # --- Request robustness ---
    request_timeout: float = 60.0        # seconds per HTTP request
    max_retries: int = 5                 # transient-failure retries per request
    retry_backoff: float = 2.0           # exponential backoff base (seconds)
    min_sleep_between_requests: float = 0.4  # politeness delay between API calls
    per_request_limit: int = 50          # pages/categories fetched per API call

    # --- Incremental sync ---
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "out")
    output_format: str = "json"          # 'json' (megafiles) + sql (PostgreSQL)

    # --- PostgreSQL (SQL persistence, "SQL + JSON in parallel" approach) ---
    database_url: str = "postgresql+asyncpg://warframe:warframe@localhost:5432/warframe_lore"

    # --- Scope ---
    # Buckets are configured externally (buckets.json), via BucketConfig — not
    # duplicated here. Namespaces to keep (0 = main/article). Everything else
    # is skipped (Talk:, User:, File:, Conclave:, etc.).
    include_namespaces: frozenset = frozenset({0})

    # Page titles / prefixes to always exclude (case-insensitive substring).
    exclude_title_parts: tuple = (
        "(quest)/",      # quotes subpages live elsewhere; we handle them explicitly
        "/gameplay",     # redundant subpages
        "transcript:",
        "dominion:",
    )

    # Whether to follow subcategories of the configured categories.
    follow_subcategories: bool = True
    # How deep to recurse into subcategories (0 = only direct members).
    max_category_depth: int = 3

    # --- Output ---
    # A megafile per bucket; files named after the bucket id.
    include_empty_buckets: bool = False


def load_config() -> Config:
    """Build a Config, applying environment-variable overrides.

    ``config.py`` is now the single entry point for ``WF_*`` variables: the
    ``.env`` file is loaded here (not via an import side-effect of ``engram``/
    ``discord``), so ``cephalon run`` sees the exact same overrides.
    """
    load_dotenv()
    cfg = Config()

    cfg.api_url = os.getenv("WF_API_URL", cfg.api_url)
    cfg.output_dir = Path(os.getenv("WF_OUTPUT_DIR", str(cfg.output_dir)))
    cfg.database_url = os.getenv("WF_DATABASE_URL", cfg.database_url)

    cfg.max_retries = int(os.getenv("WF_MAX_RETRIES", str(cfg.max_retries)))
    cfg.request_timeout = float(os.getenv("WF_TIMEOUT", str(cfg.request_timeout)))
    cfg.min_sleep_between_requests = float(
        os.getenv("WF_SLEEP", str(cfg.min_sleep_between_requests))
    )

    return cfg
