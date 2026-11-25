"""Generic language detection and URL locale filtering/deduplication."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

try:
    from langdetect import detect as _langdetect  # type: ignore[import-not-found]
except Exception:  # noqa: BLE001
    _langdetect = None

SUPPORTED_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "EN"), ("fr", "FR"), ("de", "DE"), ("es", "ES"),
    ("it", "IT"), ("pt", "PT"), ("ru", "RU"), ("ja", "JA"),
    ("ko", "KO"), ("zh", "ZH"), ("pl", "PL"),
)
DEFAULT_ALLOWED_LANGUAGES: tuple[str, ...] = ("en",)
_ISO_CODES = frozenset({
    "en", "fr", "de", "es", "it", "pt", "ru", "pl", "ja", "ko", "zh", "tr",
    "uk", "th", "nl", "sv", "fi", "no", "da", "cs", "hu", "ro", "sk", "sl",
    "bg", "el", "hr", "lt", "lv", "et", "mt", "is", "ar", "id", "vi", "hi",
})
_LOCALE_ALIASES: dict[str, str] = {
    "en-us": "en", "en-gb": "en", "en-ca": "en", "en-au": "en",
    "fr-fr": "fr", "fr-ca": "fr", "de-de": "de", "es-es": "es", "es-mx": "es",
    "es-419": "es", "it-it": "it", "pt-br": "pt", "pt-pt": "pt", "ru-ru": "ru",
    "pl-pl": "pl", "ja-jp": "ja", "jp": "ja", "ko-kr": "ko", "kr": "ko",
    "zh-cn": "zh", "zh-tw": "zh", "zh-hans": "zh", "zh-hant": "zh",
    "zh-hk": "zh", "tc": "zh", "sc": "zh", "tr-tr": "tr", "uk-ua": "uk",
    "ua": "uk", "th-th": "th",
}
_NEUTRAL_SUBDOMAINS = frozenset({
    "www", "wiki", "forums", "origin", "support", "store", "api", "static",
    "images", "img", "cdn", "content", "media", "dev", "docs", "blog",
})
_SUFFIX_RE = re.compile(r"_[a-z]{2}(?=(?:\.[a-z0-9]+)*$)", re.IGNORECASE)
URL_LANGUAGE = (
    (re.compile(r"(?:^|[/.\-?_])fr(?:[/.\-=&!]|$)"), "fr"),
    (re.compile(r"(?:^|[/.\-?_])en(?:[/.\-=&!]|$)"), "en"),
)
FRENCH_WORDS = (" le ", " la ", " les ", " des ", " et ", " une ", " est ")
ENGLISH_WORDS = (" the ", " and ", " of ", " to ", " in ", " is ", " for ")
ACCENTS = "àâçéèêëîïôûùüÿœæ"
_FR_SLUG_TOKENS = (
    "français", "francais", "atelier-des-devs", "-sauvegarde-",
    "mises-à-jour", "modifications-apportées",
    "quête-", "défi-glacial", "repoussée",
)


def _map_token(token: str) -> str | None:
    clean = token.strip().lower().replace("_", "-")
    if clean in _ISO_CODES or clean in _LOCALE_ALIASES:
        return _LOCALE_ALIASES.get(clean, clean)
    base = clean.split("-", 1)[0]
    return base if "-" in clean and len(clean) <= 7 and base in _ISO_CODES else None


def detect_url_locale(url: str) -> str | None:
    """Return explicit 2-letter language code found in ``url``, or None if neutral."""
    parsed = urlparse(str(url or "").strip())
    host_parts = (parsed.hostname or "").lower().removeprefix("www.").split(".")
    if len(host_parts) >= 3 and host_parts[0] not in _NEUTRAL_SUBDOMAINS:
        if (sub_lang := _map_token(host_parts[0])) is not None:
            return sub_lang
    segs = [s.lower() for s in parsed.path.strip("/").split("/") if s]
    if segs:
        if (first := _map_token(segs[0])) is not None:
            return first
        for idx, seg in enumerate(segs[:-1]):
            if seg in {"hc", "intl", "locale", "lang", "change_language"} and (
                second := _map_token(segs[idx + 1])
            ):
                return second
        if (m := _SUFFIX_RE.search(segs[-1].split("!", 1)[0])) and (
            suf := _map_token(m.group(0).lstrip("_"))
        ):
            return suf
    for key in ("lang", "locale", "hl", "l") if parsed.query else ():
        for val in parse_qs(parsed.query.lower()).get(key, ()):
            if (qlang := _map_token(val)) is not None:
                return qlang
    decoded = unquote(f"{parsed.path} {parsed.query}").lower()
    return "fr" if any(tok in decoded for tok in _FR_SLUG_TOKENS) else None


def normalize_allowed_languages(allowed_languages: Any = None) -> tuple[str, ...]:
    """Normalize a collection of language codes, defaulting to ('en',)."""
    val = allowed_languages or ()
    raw = val.split(",") if isinstance(val, str) else list(val)
    codes = [str(c).strip().lower()[:2] for c in raw if str(c).strip()]
    return tuple(dict.fromkeys(codes)) or DEFAULT_ALLOWED_LANGUAGES


def is_url_language_allowed(
    url: str, allowed_languages: Any = DEFAULT_ALLOWED_LANGUAGES
) -> bool:
    """Return True if ``url`` has no foreign locale or matches ``allowed_languages``."""
    allowed = set(normalize_allowed_languages(allowed_languages))
    loc = detect_url_locale(url)
    return True if "*" in allowed or "al" in allowed or loc is None else loc in allowed


def canonical_locale_url_key(url: str) -> str:
    """Return a locale-stripped URL key so translated sibling URLs deduplicate."""
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.rstrip("/").lower()
    host = (parsed.hostname or "").lower().removeprefix("www.")
    segs = [s for s in parsed.path.strip("/").split("/") if s]
    if segs and _map_token(segs[0]) is not None:
        segs = segs[1:]
    elif len(segs) >= 2 and segs[0].lower() in {"hc", "intl"} and _map_token(segs[1]):
        segs = [segs[0], *segs[2:]]
    q = f"?{parsed.query.lower()}" if parsed.query else ""
    return f"{host}/{'/'.join(segs).lower()}{q}".rstrip("/")


def detect_language(url: str, text: str = "", declared: str = "") -> str:
    """Return the best-supported language code for a collected page."""
    code = declared.strip().lower().replace("_", "-")[:2]
    if code in {"fr", "en"}:
        return code
    if (url_loc := detect_url_locale(url)) in {"fr", "en"}:
        return str(url_loc)
    for pattern, language in URL_LANGUAGE:
        if pattern.search(url.lower()):
            return language
    return _from_text(text)


def _from_text(text: str) -> str:
    sample = text[:4000]
    if len(sample.strip()) >= 40 and _langdetect is not None:
        try:
            detected = str(_langdetect(sample)).strip().lower()[:2]
            if detected in {"fr", "en"}:
                return detected
        except Exception:  # noqa: BLE001
            pass
    low = sample[:2000].lower()
    fr = sum(low.count(w) for w in FRENCH_WORDS)
    en = sum(low.count(w) for w in ENGLISH_WORDS)
    if fr == en:
        fr += sum(low.count(c) for c in ACCENTS)
    return "fr" if fr > en else "en"
