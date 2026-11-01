import json
import os
import queue
import threading
import time
from pathlib import Path

import i18n
import pytest

from helpers import load_module

status = load_module("waybar_player_status", "bin/waybar-player-status")


@pytest.fixture(autouse=True)
def _russian_language():
    previous = i18n.language()
    i18n.set_language("ru")
    yield
    i18n.set_language(previous)


def test_marquee_keeps_short_title():
    assert status.marquee("short", 5, 30) == "short"


def test_marquee_window_and_wrap():
    text = "abcdefghij"
    assert status.marquee(text, 0, 5) == "abcde"
    assert status.marquee(text, 1, 5) == "bcdef"
    loop_len = len(text + "   •   ")
    assert status.marquee(text, loop_len, 5) == "abcde"
    assert len(status.marquee("x" * 100, 7, 30)) == 30


def test_volume_percent_matches_old_shell_logic():
    assert status.volume_percent("0.42") == 42
    assert status.volume_percent("1.0") == 100
    assert status.volume_percent("0.07") == 7
    assert status.volume_percent("0.999") == 99
    assert status.volume_percent("") is None
    assert status.volume_percent("oops") is None


def _state(**overrides):
    base = {
        "status": "playing",
        "player": "chromium",
        "title": "Track",
        "artist": "Artist",
        "album": "Album",
        "art_url": "",
        "volume": "0.42",
    }
    base.update(overrides)
    return base


def test_status_json_playing():
    payload = json.loads(status.status_json(_state(), 0, 0, 30))
    assert payload["class"] == "playing"
    assert payload["text"].startswith("◐  Track")
    assert payload["percentage"] == 42
    assert "Плеер: chromium" in payload["tooltip"]
    assert "Громкость: 42%" in payload["tooltip"]
    assert "Состояние: Играет" in payload["tooltip"]
    assert "Колесо — громкость" in payload["tooltip"]


def test_status_json_paused():
    payload = json.loads(status.status_json(_state(status="paused"), 0, 0, 30))
    assert payload["class"] == "paused"
    assert payload["text"] == "󰏤  Track"


def test_status_json_stopped_without_title():
    payload = json.loads(
        status.status_json(_state(status="stopped", title="", artist="", album=""), 0, 0, 30)
    )
    assert payload["class"] == "stopped"
    assert payload["text"] == "󰏤  Остановлено"
    assert payload["tooltip"].startswith("Остановлено")


def test_status_json_no_player():
    payload = json.loads(status.status_json(None, 0, 0, 30))
    assert payload["class"] == "stopped"
    assert payload["text"] == "󰎆"
    assert "Нет активного MPRIS-плеера" in payload["tooltip"]
    assert "percentage" not in payload


def test_status_json_without_volume_has_no_percentage():
    payload = json.loads(status.status_json(_state(volume=""), 0, 0, 30))
    assert "percentage" not in payload


def test_status_json_handles_special_characters():
    state = _state(title='A & B "quoted" <tag>', artist="AC/DC")
    payload = json.loads(status.status_json(state, 0, 0, 30))
    assert "\"text\"" in status.status_json(state, 0, 0, 30)
    assert payload["tooltip"].startswith('A & B "quoted" <tag>')


class FakeMprisPlayer:
    base_name = "chromium"
    status = "playing"
    volume = 0.5
    shuffle = False
    loop = "track"
    can_next = True
    can_previous = True
    can_pause = True
    can_control = True

    def title(self):
        return "Title"

    def artist(self):
        return "Artist"

    def album(self):
        return "Album"

    def art_url(self):
        return "https://example/cover"

    def track_id(self):
        return "track-1"

    def track_url(self):
        return "https://example/track"

    def length(self):
        return 100.0


def test_parse_metadata_line():
    state = status.state_from_player(FakeMprisPlayer())
    assert state["status"] == "playing"
    assert state["player"] == "chromium"
    assert state["title"] == "Title"
    assert state["volume"] == "0.500000"


def test_follow_format_requests_volume():
    assert status.volume_percent("0.500000") == 50
    state = status.state_from_player(FakeMprisPlayer())
    assert status.volume_percent(state["volume"]) == 50


def test_volume_change_changes_percentage():
    low = json.loads(status.status_json(_state(volume="0.10"), 0, 0, 30))
    high = json.loads(status.status_json(_state(volume="0.80"), 0, 0, 30))
    assert low["percentage"] == 10
    assert high["percentage"] == 80


def test_resync_interval_is_thirty_seconds():
    assert status.RESYNC_MS == 30_000
    assert status.DEBOUNCE_MS == 50


def test_status_does_not_use_playerctl():
    source = Path(status.__file__).read_text(encoding="utf-8")
    assert "playerctl" not in source


def test_status_transition_playing_paused_playing():
    playing = json.loads(status.status_json(_state(status="playing"), 0, 0, 30))
    paused = json.loads(status.status_json(_state(status="paused"), 0, 0, 30))
    playing_again = json.loads(status.status_json(_state(status="playing"), 1, 0, 30))

    assert playing["class"] == "playing"
    assert playing["text"].startswith("◐")
    assert paused["class"] == "paused"
    assert paused["text"].startswith("󰏤")
    assert playing_again["class"] == "playing"
    assert playing_again["text"].startswith("◓")


def test_two_players_selected_pause_changes_class():
    statuses = {"A": "playing", "B": "paused"}
    selected = status.players.select_player(["A", "B"], statuses, current="A")
    assert selected == "A"
    assert json.loads(status.status_json(_state(status="playing"), 0, 0, 30))["class"] == "playing"

    statuses["A"] = "paused"
    selected = status.players.select_player(["A", "B"], statuses, current="A")
    assert selected == "A"
    assert json.loads(status.status_json(_state(status="paused"), 0, 0, 30))["class"] == "paused"


def test_non_selected_pause_does_not_change_selection():
    statuses = {"A": "playing", "B": "paused"}
    selected = status.players.select_player(["A", "B"], statuses, current="A")
    playing = json.loads(status.status_json(_state(status="playing"), 0, 0, 30))
    statuses["B"] = "paused"
    assert status.players.select_player(["A", "B"], statuses, current=selected) == "A"
    assert playing["class"] == "playing"
