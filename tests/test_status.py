import json

from helpers import load_module

status = load_module("waybar_player_status", "bin/waybar-player-status")


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


def test_parse_metadata_line():
    line = "\x1f".join(
        ["Playing", "chromium", "Title", "Artist", "Album", "https://example/cover", "0.5"]
    )
    state = status.parse_metadata_line(line)
    assert state["status"] == "playing"
    assert state["player"] == "chromium"
    assert state["title"] == "Title"
    assert state["volume"] == "0.5"
