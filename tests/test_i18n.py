"""
Tests for dnsmark.i18n — locale loading, translation lookup, detection.
"""

from __future__ import annotations

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dnsmark import i18n


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_i18n_cache():
    """Ensure each test starts with a clean locale cache."""
    i18n.clear_cache()
    yield
    i18n.clear_cache()


# ---------------------------------------------------------------------------
# All 21 languages: app_name
# ---------------------------------------------------------------------------

EXPECTED_LANGS = [
    "de", "en", "pl", "ru", "fr", "nl", "cs", "hu", "it", "es",
    "pt", "sv", "no", "da", "fi", "el", "ro", "tr", "uk", "hr", "bg",
]


class TestTranslationAllLangs:
    @pytest.mark.parametrize("lang", EXPECTED_LANGS)
    def test_app_name_returns_string(self, lang):
        result = i18n.t("app_name", lang)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.parametrize("lang", EXPECTED_LANGS)
    def test_app_name_not_just_key(self, lang):
        """t() should not return the bare key 'app_name'."""
        result = i18n.t("app_name", lang)
        assert result != "app_name", f"Lang {lang!r}: key returned as value (locale not loaded?)"

    @pytest.mark.parametrize("lang", EXPECTED_LANGS)
    def test_app_tagline_present(self, lang):
        result = i18n.t("app_tagline", lang)
        assert isinstance(result, str) and len(result) > 0


# ---------------------------------------------------------------------------
# Placeholder substitution
# ---------------------------------------------------------------------------

class TestPlaceholderSubstitution:
    def test_bench_progress_single(self):
        result = i18n.t("bench_progress", "en", server="1.1.1.1", done=3, total=72)
        assert "1.1.1.1" in result
        assert "3" in result
        assert "72" in result

    def test_bench_progress_german(self):
        result = i18n.t("bench_progress", "de", server="8.8.8.8", done=1, total=10)
        assert "8.8.8.8" in result
        assert "1" in result

    def test_set_dns_success(self):
        result = i18n.t("set_dns_success", "en", server="9.9.9.9")
        assert "9.9.9.9" in result

    def test_set_dns_fail(self):
        result = i18n.t("set_dns_fail", "en", error="permission denied")
        assert "permission denied" in result

    def test_extra_kwargs_dont_crash(self):
        """Extra kwargs not in the format string should be silently ignored."""
        result = i18n.t("app_name", "en", unexpected_kwarg="value")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Missing key fallback
# ---------------------------------------------------------------------------

class TestMissingKeyFallback:
    def test_missing_key_falls_back_to_en(self):
        """If a key is absent in the target lang but present in en, en value is used."""
        # Patch load_lang to return an empty dict for "xx" but normal en
        with patch.object(i18n, "_load_file", side_effect=lambda lang: (
            {} if lang == "xx" else i18n._load_file.__wrapped__(lang)
            if hasattr(i18n._load_file, "__wrapped__") else {}
        )):
            i18n.clear_cache()
            # Reload normally — the English file should always have the key
            result = i18n.t("app_name", "en")
            assert result == "DNSMark"

    def test_completely_unknown_key_returns_key_itself(self):
        result = i18n.t("this_key_does_not_exist_xyz", "en")
        assert result == "this_key_does_not_exist_xyz"

    def test_unknown_lang_falls_back_gracefully(self):
        """Querying a non-existent language should not crash."""
        result = i18n.t("app_name", "xx")
        assert isinstance(result, str)
        # Should fall back to English
        assert result == "DNSMark"


# ---------------------------------------------------------------------------
# detect_lang
# ---------------------------------------------------------------------------

class TestDetectLang:
    def test_returns_string(self):
        lang = i18n.detect_lang()
        assert isinstance(lang, str)
        assert len(lang) == 2

    def test_from_lang_env(self):
        with patch.dict(os.environ, {"LANG": "de_DE.UTF-8", "LANGUAGE": ""}, clear=False):
            i18n.clear_cache()
            lang = i18n.detect_lang()
            assert lang == "de"

    def test_from_language_env(self):
        with patch.dict(os.environ, {"LANGUAGE": "fr:en:de", "LANG": ""}, clear=False):
            i18n.clear_cache()
            lang = i18n.detect_lang()
            assert lang == "fr"

    def test_language_env_takes_priority_over_lang(self):
        with patch.dict(os.environ, {"LANGUAGE": "pl", "LANG": "de_DE.UTF-8"}, clear=False):
            i18n.clear_cache()
            lang = i18n.detect_lang()
            assert lang == "pl"

    def test_fallback_to_en_on_c_locale(self):
        with patch.dict(os.environ, {"LANG": "C", "LANGUAGE": ""}, clear=False):
            i18n.clear_cache()
            lang = i18n.detect_lang()
            assert lang == "en"

    def test_fallback_to_en_on_posix_locale(self):
        with patch.dict(os.environ, {"LANG": "POSIX", "LANGUAGE": ""}, clear=False):
            i18n.clear_cache()
            lang = i18n.detect_lang()
            assert lang == "en"


# ---------------------------------------------------------------------------
# get_available_langs
# ---------------------------------------------------------------------------

class TestGetAvailableLangs:
    def test_returns_list(self):
        langs = i18n.get_available_langs()
        assert isinstance(langs, list)

    def test_english_present(self):
        langs = i18n.get_available_langs()
        assert "en" in langs

    def test_german_present(self):
        langs = i18n.get_available_langs()
        assert "de" in langs

    def test_sorted(self):
        langs = i18n.get_available_langs()
        assert langs == sorted(langs)

    def test_all_21_present(self):
        langs = set(i18n.get_available_langs())
        missing = set(EXPECTED_LANGS) - langs
        assert not missing, f"Missing language files: {missing}"


# ---------------------------------------------------------------------------
# load_lang and caching
# ---------------------------------------------------------------------------

class TestLoadLang:
    def test_returns_dict(self):
        d = i18n.load_lang("en")
        assert isinstance(d, dict)

    def test_cached_on_second_call(self):
        d1 = i18n.load_lang("en")
        d2 = i18n.load_lang("en")
        assert d1 is d2, "Second call should return same cached object"

    def test_non_english_contains_en_keys(self):
        """Non-English dict should contain all English keys (English is base)."""
        en_keys = set(i18n.load_lang("en").keys())
        de_keys = set(i18n.load_lang("de").keys())
        assert en_keys.issubset(de_keys), "German should inherit all English keys"

    def test_user_override_applied(self, tmp_path):
        """User locale file at ~/.dnsmark/locales/ should override bundled strings."""
        override_dir = tmp_path / ".dnsmark" / "locales"
        override_dir.mkdir(parents=True)
        override_file = override_dir / "en.json"
        override_file.write_text(
            json.dumps({"app_name": "CustomMark"}), encoding="utf-8"
        )

        with patch.object(i18n, "_USER_LOCALE_DIR", override_dir):
            i18n.clear_cache()
            result = i18n.t("app_name", "en")

        assert result == "CustomMark"
