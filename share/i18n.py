"""Tiny JSON-based i18n for waybar-player (no gettext).

Language order: WAYBAR_PLAYER_LANG, LC_ALL, LC_MESSAGES, LANG.
Only the first two letters are used; unknown languages fall back to English.
"""

import json
import os
from pathlib import Path

SUPPORTED = ("en", "ru")
DEFAULT = "en"

_HERE = Path(__file__).resolve().parent
_LOCALE_CANDIDATES = (
    _HERE / "locales",
    _HERE.parent / "locales",
    Path("/usr/share/waybar-player/locales"),
)
_catalogs = {}


def _locale_dir():
    for candidate in _LOCALE_CANDIDATES:
        if (candidate / "en.json").is_file():
            return candidate
    return _LOCALE_CANDIDATES[0]


def _code(value):
    return (value or "").strip().split("_")[0].split(".")[0].lower()


def normalize_language(value):
    code = _code(value)
    return code if code in SUPPORTED else DEFAULT


def detect_language():
    for name in ("WAYBAR_PLAYER_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(name)
        if value:
            return normalize_language(value)
    return DEFAULT


_language = detect_language()


def language():
    return _language


def set_language(value=None):
    global _language
    _language = detect_language() if value is None else normalize_language(value)
    return _language


def _catalog(lang):
    lang = normalize_language(lang)
    if lang not in _catalogs:
        try:
            with (_locale_dir() / (lang + ".json")).open(encoding="utf-8") as handle:
                _catalogs[lang] = json.load(handle)
        except (OSError, ValueError):
            _catalogs[lang] = {}
    return _catalogs[lang]


def _translate(key, lang, **kwargs):
    template = _catalog(lang).get(key)
    if template is None:
        template = _catalog(DEFAULT).get(key)
    if template is None:
        return key
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def t(key, **kwargs):
    return _translate(key, _language, **kwargs)
