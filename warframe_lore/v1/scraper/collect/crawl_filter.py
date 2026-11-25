"""Generic URL path filtering and feed/sitemap hint extraction for HTML crawls."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from .language import detect_url_locale, is_url_language_allowed

_LOCALE_SEGMENTS = frozenset({
    "en", "fr", "de", "es", "it", "pt", "ru", "ja", "ko", "zh", "pl", "nl",
})
_CDN_ASSET_HOSTS = (
    "nocookie.net", "images.wikia.com", "static.wikia.com",
)
GENERALIST_DOMAINS = (
    "wikipedia.org", "wikimedia.org", "wikidata.org", "wiktionary.org",
    "youtube.com", "youtu.be", "reddit.com", "github.com", "gitlab.com",
    "archive.org", "steamcommunity.com", "steampowered.com", "twitter.com",
    "x.com", "facebook.com", "instagram.com", "twitch.tv", "discord.com",
    "discord.gg", "apple.com", "deezer.com", "spotify.com", "microsoft.com",
    "playstation.com", "nintendo.com", "google.com", "developpez.com",
    "radiofrance.fr", "europa.eu", "froala.com",
)
_WIKI_META_TOKENS = (
    "/wiki/special:", "/wiki/spécial:", "/wiki/sp%c3%a9cial:",
    "/wiki/talk:", "/wiki/discussion:", "/wiki/discussion_",
    "/wiki/portal:", "/wiki/portail:", "/wiki/projet:", "/wiki/project:",
    "/wiki/category:", "/wiki/catégorie:", "/wiki/cat%c3%a9gorie:",
    "/wiki/file:", "/wiki/fichier:", "/wiki/help:", "/wiki/aide:",
    "/wiki/wikipedia:", "/wiki/wikipédia:", "/wiki/template:", "/wiki/modèle:",
    "/pulls", "/issues", "/forks", "/security", "/insights", "/pulse",
    "/projects", "/actions", "/activity", "/branches", "/tags", "/commits/",
    "/custom-properties", "/contact/report-content", "/tree/master/.",
    "/tree/main/.", "/blob/master/.", "/blob/main/.", "/dockerfile",
    "/docker-compose", "/requirements.txt", "/eslint.config", "/nyc.config",
    "/license", "/contributing.md", ".bat", ".py", ".ts", ".mjs",
)
NOISE_PATH_SEGMENTS = (
    "/login", "/signin", "/sign-in", "/signup", "/sign-up", "/register",
    "/logout", "/cart", "/checkout", "/shop", "/store", "/account",
    "/promocode", "/promo-code", "/download", "/privacy", "/terms",
    "/cookies", "/cookie", "/oauth", "/auth", "/pricing", "/billing",
    "/password", "/resetpassword", "/subscribe", "/unsubscribe", "/products/",
    "/collections/", "/pages/sizing", "/pages/shipping", "/pages/policies",
    "/pages/contact", "/.well-known/", "/change_language/", "/theming_assets/",
    "/related/click", "/requests/new", "/subscription.html", "/attachment.php",
    "/twitch/link_action", "/user", "/zendesk", "/supporter-packs",
    "/prime-access", "/prime-resurgence", "/heirloom", "/steamworkshop",
    "/crossprogression", "/mobile", "/android", "/ios", "$", "action=edit",
    ".oembed", ".atom", ".png", ".jpg", ".jpeg", ".gif", ".webp",
)
_FEED_LINK_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def infer_path_prefix(seed_url: str, configured: str = "") -> str:
    """Return an explicit prefix or infer a 2-letter locale prefix like /en."""
    if configured.strip():
        return "/" + configured.strip().strip("/")
    path = urlparse(seed_url).path.strip("/")
    first = path.split("/", 1)[0].lower() if path else ""
    return f"/{first}" if first in _LOCALE_SEGMENTS and "/" not in path else ""


def keep_crawl_url(
    url: str, seed_url: str, *, prefix: str = "",
    extra_excludes: tuple[str, ...] = (), allowed_languages: Any = None,
) -> bool:
    """Return True when ``url`` is within prefix, allowed language and not noise."""
    parsed = urlparse(url)
    if any(cdn in parsed.netloc.lower() for cdn in _CDN_ASSET_HOSTS):
        return False
    if allowed_languages is not None:
        langs: Any = allowed_languages
    else:
        seed_loc = detect_url_locale(seed_url)
        langs = ("en", seed_loc) if seed_loc and seed_loc != "en" else ("en",)
    if not is_url_language_allowed(url, langs):
        return False
    path = parsed.path.lower().rstrip("/") or "/"
    seed_path = (
        urlparse(seed_url).path.lower().rstrip("/") or "/"
        if seed_url and seed_url != url else ""
    )
    if prefix and not (path == prefix or path.startswith(f"{prefix}/")):
        return False
    excludes = NOISE_PATH_SEGMENTS + tuple(e.lower() for e in extra_excludes if e)
    return not any(seg in path and seg not in seed_path for seg in excludes)


def extract_alternate_feeds(html: str, base_url: str) -> list[str]:
    """Return RSS/Atom feed URLs advertised by <link rel='alternate'> tags."""
    out: list[str] = []
    for match in _FEED_LINK_RE.finditer(html):
        tag = match.group(0).lower()
        if "rss" not in tag and "atom" not in tag and "xml" not in tag:
            continue
        href = urljoin(base_url, match.group(1).strip())
        if href.startswith(("http://", "https://")) and href not in out:
            out.append(href)
    return out


def is_generalist_domain(url_or_host: str) -> bool:
    """Return True for multi-topic platforms (Wikipedia, YouTube, GitHub, etc.)."""
    raw = str(url_or_host or "").strip().lower()
    host = (urlparse(raw).hostname or raw).lower().removeprefix("www.")
    if not host:
        return False
    if host in {"fandom.com", "wikia.com", "wiki.gg"}:
        return True
    return any(host == dom or host.endswith(f".{dom}") for dom in GENERALIST_DOMAINS)


def matches_universe_topic(
    url: str, title: str = "", keywords: list[str] | tuple[str, ...] = ()
) -> bool:
    """Return True when ``url`` or ``title`` explicitly matches universe keywords."""
    decoded_url = unquote(str(url or "")).lower()
    if any(tok in decoded_url for tok in _WIKI_META_TOKENS):
        return False
    needles = [
        str(k).strip().lower() for k in keywords if len(str(k).strip()) >= 3
    ]
    if not needles:
        return True
    parsed = urlparse(decoded_url)
    hay = f"{parsed.path} {parsed.query} {unquote(str(title or '')).lower()}"
    hay_norm = re.sub(r"[_\-/+.,:;!?()\[\]]+", " ", hay)
    return any(n in hay or n in hay_norm for n in needles)


def matches_topic_tags(tags: list[str] | tuple[str, ...], *texts: str) -> bool:
    """Return True when no tags are set or any tag appears in ``texts``."""
    needles = [str(t).strip().lower() for t in tags if str(t).strip()]
    if not needles:
        return True
    haystack = " ".join(str(part or "") for part in texts).lower()
    return any(needle in haystack for needle in needles)


def allow_child_crawl(
    url: str, seed_url: str, limits: dict[str, Any],
    *, prefix: str = "", extra_excludes: tuple[str, ...] = (), title: str = "",
) -> bool:
    """Enforce generalist-domain topic guard, language filter and path rules."""
    raw_kw = limits.get("universe_keywords") or limits.get("topic_tags") or []
    u_kw = [str(k).strip() for k in raw_kw if str(k).strip()]
    if is_generalist_domain(seed_url) and not (
        u_kw and matches_universe_topic(url, title, u_kw)
    ):
        return False
    langs = limits.get("allowed_languages")
    return keep_crawl_url(
        url, seed_url, prefix=prefix,
        extra_excludes=extra_excludes, allowed_languages=langs,
    )
