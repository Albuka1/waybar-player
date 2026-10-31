import json
import string
from pathlib import Path

import i18n
import pytest

LOCALES = Path(__file__).resolve().parents[1] / "locales"

EXPECTED_RU = {
    "menu.title": "Медиаплеер",
    "menu.close": "Закрыть (Esc)",
    "menu.prev": "Предыдущий трек",
    "menu.play_pause": "Плей/Пауза",
    "menu.next": "Следующий трек",
    "menu.volume": "Громкость",
    "menu.status": "{player} • {status}",
    "menu.play": "Играть",
    "menu.pause": "Пауза",
    "player.unavailable": "Плеер недоступен",
    "player.no_active": "Нет активного MPRIS-плеера",
    "status.playing": "Играет",
    "status.paused": "Пауза",
    "status.stopped": "Остановлен",
    "status.no_title": "Без названия",
    "status.stopped_text": "Остановлено",
    "status.no_player_hint": "Нет активного MPRIS-плеера\n\nЛКМ — открыть меню",
    "status.player": "Плеер: {player}",
    "status.volume": "Громкость: {pct}%",
    "status.state": "Состояние: {status}",
    "status.hints": "ЛКМ — меню • СКМ — предыдущий • ПКМ — пауза/плей",
    "status.scroll_hint": "Колесо — громкость",
}


def _load(name):
    return json.loads((LOCALES / (name + ".json")).read_text(encoding="utf-8"))


def _placeholders(template):
    return {
        name
        for _, name, _, _ in string.Formatter().parse(template)
        if name is not None
    }


@pytest.fixture(autouse=True)
def _restore_language():
    previous = i18n.language()
    yield
    i18n.set_language(previous)


def test_catalogs_have_same_keys_and_placeholders():
    en = _load("en")
    ru = _load("ru")
    assert set(en) == set(ru)
    assert len(en) == 22
    for key in en:
        assert _placeholders(en[key]) == _placeholders(ru[key]), key


def test_russian_catalog_matches_reference():
    assert _load("ru") == EXPECTED_RU


def test_unknown_language_falls_back_to_english():
    i18n.set_language("de")
    assert i18n.language() == "en"
    assert i18n.t("menu.title") == "Media player"


def test_missing_key_falls_back_to_english(monkeypatch):
    i18n.set_language("ru")
    i18n._catalog("ru")
    monkeypatch.setitem(i18n._catalogs, "ru", {})
    assert i18n.t("menu.title") == "Media player"


def test_waybar_player_lang_override(monkeypatch):
    monkeypatch.setenv("WAYBAR_PLAYER_LANG", "ru")
    i18n.set_language()
    assert i18n.language() == "ru"
    assert i18n.t("menu.title") == "Медиаплеер"


def test_language_detection_order(monkeypatch):
    for name in ("WAYBAR_PLAYER_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    i18n.set_language()
    assert i18n.language() == "ru"

    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    i18n.set_language()
    assert i18n.language() == "en"


def test_formatting_and_missing_key():
    i18n.set_language("ru")
    assert i18n.t("menu.status", player="vlc", status="Пауза") == "vlc • Пауза"
    assert i18n.t("status.volume", pct=42) == "Громкость: 42%"
    assert i18n.t("no.such.key") == "no.such.key"
