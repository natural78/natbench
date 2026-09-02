"""
dnsmark.i18n — Internationalization
=====================================
Loads translation strings from external JSON locale files.

Search order for a given language code (first match merged with 'en' base):
  1. <package>/dnsmark/locales/{lang}.json   — bundled locales
  2. ~/.dnsmark/locales/{lang}.json          — user overrides (takes priority)

The module keeps a process-level cache to avoid re-reading files on every call.

Public API
----------
::

    from dnsmark.i18n import t, detect_lang, get_available_langs, load_lang

    lang = detect_lang()                      # "de" / "en" / ...
    name = t("app_name", lang)                # "DNSMark"
    msg  = t("bench_progress", lang,          # "Testing example.com (3/72)"
              server="example.com", done=3, total=72)

    langs = get_available_langs()             # ["bg", "cs", "da", ...]
"""

from __future__ import annotations

import json
import locale
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

#: Process-level cache: lang_code -> merged string dict
_cache: dict[str, dict[str, str]] = {}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

#: Directory of bundled locale JSON files  (next to this .py file)
_BUILTIN_LOCALE_DIR = Path(__file__).parent / "locales"

#: User locale override directory
_USER_LOCALE_DIR = Path.home() / ".dnsmark" / "locales"


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_available_langs() -> list[str]:
    """Return sorted list of all available language codes (builtin + user)."""
    langs: set[str] = set()

    for d in (_BUILTIN_LOCALE_DIR, _USER_LOCALE_DIR):
        if d.is_dir():
            for f in d.glob("*.json"):
                if not f.stem.startswith("_"):
                    langs.add(f.stem)

    return sorted(langs)


def load_lang(lang: str) -> dict[str, str]:
    """Load and return the merged string dict for *lang*.

    Always includes all keys from the English baseline, with *lang*-specific
    strings overlaid on top.  The result is cached indefinitely.
    """
    if lang in _cache:
        return _cache[lang]

    # Load English base first (always available)
    base: dict[str, str] = _load_file("en")

    if lang == "en":
        _cache["en"] = base
        return base

    # Load target language and overlay on base
    target = _load_file(lang)
    merged = {**base, **target}

    _cache[lang] = merged
    return merged


def t(key: str, lang: str = "en", **kwargs: object) -> str:
    """Return the translated string for *key* in *lang*.

    Falls back to English if *key* is not found in *lang*.
    Applies ``str.format(**kwargs)`` for placeholder substitution.

    Parameters
    ----------
    key:
        Translation key, e.g. ``"app_name"``, ``"bench_progress"``.
    lang:
        ISO-639-1 language code.
    **kwargs:
        Named placeholders that are substituted into the string, e.g.
        ``server="1.1.1.1", done=3, total=72``.

    Returns
    -------
    str
        Translated (and formatted) string, or *key* itself as a last resort.
    """
    strings = load_lang(lang)

    # Try target lang, fall back to English, fall back to key itself
    text = strings.get(key)
    if text is None:
        en_strings = load_lang("en")
        text = en_strings.get(key, key)

    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass  # Return unformatted rather than crash

    return text


def detect_lang() -> str:
    """Detect the user's preferred language from the environment.

    Checks (in order):
    1. ``LANGUAGE`` env var (colon-separated list, first entry used)
    2. ``LANG`` env var
    3. ``locale.getdefaultlocale()``
    4. Falls back to ``"en"``

    Returns the 2-letter ISO-639-1 code (lowercase), e.g. ``"de"``.
    """
    available = set(get_available_langs()) or {"en"}

    for env_var in ("LANGUAGE", "LANG"):
        val = os.environ.get(env_var, "")
        if val:
            # LANGUAGE may be "de:en:fr"
            for part in val.split(":"):
                code = _extract_lang_code(part)
                if code and code in available:
                    return code
                # Try just the 2-char prefix even if not exact match
                if code:
                    return code

    # stdlib fallback
    try:
        lc, _ = locale.getdefaultlocale()
        if lc:
            code = _extract_lang_code(lc)
            if code:
                return code
    except Exception:
        pass

    return "en"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_lang_code(lang_str: str) -> Optional[str]:
    """Extract 2-letter lowercase code from strings like 'de_DE.UTF-8' or 'de'."""
    if not lang_str or lang_str in ("C", "POSIX"):
        return None
    # Strip encoding: de_DE.UTF-8 → de_DE
    code = lang_str.split(".")[0]
    # Strip region: de_DE → de
    code = code.split("_")[0].split("-")[0].lower()
    if len(code) == 2 and code.isalpha():
        return code
    return None


def _load_file(lang: str) -> dict[str, str]:
    """Load a single locale JSON file, returning {} on any error.

    Merges builtin and user files: user file values override builtin.
    """
    result: dict[str, str] = {}

    for locale_dir in (_BUILTIN_LOCALE_DIR, _USER_LOCALE_DIR):
        path = locale_dir / f"{lang}.json"
        if path.is_file():
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    # Skip the _meta key — it's not a translation string
                    strings = {k: v for k, v in data.items()
                               if not k.startswith("_") and isinstance(v, str)}
                    result.update(strings)
            except Exception as exc:
                log.warning("i18n: failed to load %s: %s", path, exc)

    return result


def clear_cache() -> None:
    """Clear the in-process locale cache (useful for testing or hot-reload)."""
    _cache.clear()
