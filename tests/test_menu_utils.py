import base64
import colorsys
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from helpers import load_module

menu = load_module("waybar_player_menu", "share/player-menu.py")


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "0:00"),
        (0, "0:00"),
        (59, "0:59"),
        (60, "1:00"),
        (3599, "59:59"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
        ("bogus", "0:00"),
    ],
)
def test_fmt_time(value, expected):
    assert menu.fmt_time(value) == expected


@pytest.mark.parametrize(
    "pct,expected",
    [
        (0, "󰝟"),
        (1, "󰕿"),
        (33, "󰕿"),
        (34, "󰖀"),
        (66, "󰖀"),
        (67, "󰕾"),
        (100, "󰕾"),
    ],
)
def test_volume_icon(pct, expected):
    assert menu.volume_icon(pct) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("0", 0.0),
        ("1000000", 1.0),
        ("250405095", 250.405095),
        ("-5000000", 0.0),
        ("not-a-number", None),
    ],
)
def test_to_seconds(raw, expected):
    assert menu.to_seconds(raw) == expected


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/cover.png",
        "http://192.168.1.20/cover.png",
        "file:///tmp/cover.png",
        "file:///etc/passwd",
        "https://127.0.0.1/cover.png",
        "https://10.0.0.5/cover.png",
        "https://[::1]/cover.png",
    ],
)
def test_fetch_art_rejects_local_and_plain_http(url):
    assert menu.fetch_art(url) is None


def test_validate_art_url_scheme():
    assert menu.validate_art_url("file:///tmp/cover.png") is False
    assert menu.validate_art_url("http://example.com/cover.png") is False
    assert menu.validate_art_url("") is False


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nK0AAAAASUVORK5CYII="
)


def _png_in(directory, name="cover.png"):
    path = Path(directory) / name
    path.write_bytes(PNG_1X1)
    return path


def test_fetch_art_accepts_image_in_tmp():
    directory = tempfile.mkdtemp(dir="/tmp")
    try:
        path = _png_in(directory)
        assert menu.fetch_art(path.as_uri()) == str(path.resolve())
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_fetch_art_rejects_symlink_outside_whitelist():
    inside = tempfile.mkdtemp(dir="/tmp")
    outside = tempfile.mkdtemp(dir="/var/tmp")
    try:
        target = _png_in(outside, "outside.png")
        link = Path(inside) / "link.png"
        os.symlink(target, link)
        assert menu.fetch_art(link.as_uri()) is None
    finally:
        shutil.rmtree(inside, ignore_errors=True)
        shutil.rmtree(outside, ignore_errors=True)


def test_fetch_art_rejects_non_image_in_tmp():
    directory = tempfile.mkdtemp(dir="/tmp")
    try:
        path = Path(directory) / "not-image.png"
        path.write_text("not an image", encoding="utf-8")
        assert menu.fetch_art(path.as_uri()) is None
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.mark.parametrize(
    "value,expected",
    [("On", "on"), ("off", "off"), ("", None), ("bogus", None)],
)
def test_parse_shuffle(value, expected):
    assert menu.parse_shuffle(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("None", "none"),
        ("Track", "track"),
        ("Playlist", "playlist"),
        ("", None),
        ("bogus", None),
    ],
)
def test_parse_loop(value, expected):
    assert menu.parse_loop(value) == expected


def test_loop_cycle_and_commands():
    assert menu.next_loop("none") == "track"
    assert menu.next_loop("track") == "playlist"
    assert menu.next_loop("playlist") == "none"
    assert menu.next_loop(None) is None
    assert menu.loop_command("none") == "None"
    assert menu.loop_command("track") == "Track"
    assert menu.loop_command("playlist") == "Playlist"
    assert menu.loop_command(None) is None


def test_readable_accent_brightens_dark_colour():
    color = menu.readable_accent(8, 8, 8)
    assert color.startswith("#") and len(color) == 7
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    _, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    assert lightness >= 0.59
    assert saturation >= 0.54


def test_readable_accent_keeps_orange_readable():
    color = menu.readable_accent(255, 140, 0)
    assert color != "#000000"


def test_accent_foreground_uses_contrast():
    assert menu.accent_foreground("#000000") == "#ffffff"
    assert menu.accent_foreground("#ffffff") == "#000000"
    assert menu.accent_foreground("#ff8c00") == "#000000"
    assert menu.accent_soft("#ff8c00") == "rgba(255, 140, 0, 0.18)"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Volume: 0.42", 0.42),
        ("Volume: 1.00 [MUTED]", 1.0),
        ("Volume: 0.0", 0.0),
        ("", None),
        ("no volume", None),
    ],
)
def test_parse_wpctl_volume(text, expected):
    assert menu.parse_wpctl_volume(text) == expected


def test_volume_readback_matches():
    assert menu.volume_readback_matches(0.30, 0.30)
    assert not menu.volume_readback_matches(1.0, 0.30)
    assert not menu.volume_readback_matches(None, 0.30)


def test_volume_track_key_preference():
    base = {"player": "chromium", "title": "Title", "artist": "Artist"}
    assert menu.volume_track_key(dict(base, track_id="track-a")) == "chromium|track-a"
    assert menu.volume_track_key(dict(base, track_url="https://x/y")) == "chromium|https://x/y"
    assert menu.volume_track_key(base) == "chromium|Title|Artist"


def test_volume_mode_for_fixed_modes():
    assert menu.volume_mode_for("player", "playing", True) == "player"
    assert menu.volume_mode_for("sink", "paused", False, have_wpctl=True) == "sink"
    assert menu.volume_mode_for("sink", "paused", False, have_wpctl=False) == "hidden"
    assert menu.volume_mode_for("hide", "playing", False) == "hidden"


def test_volume_mode_for_pause_and_track_change():
    key_a = menu.volume_track_key({"player": "chromium", "track_id": "A"})
    key_b = menu.volume_track_key({"player": "chromium", "track_id": "B"})
    assert key_a != key_b
    # A was marked ineffective; B is a different track and must be native.
    assert menu.volume_mode_for("auto", "playing", key_a == key_b, "sink", True) == "player"
    assert menu.volume_mode_for("auto", "playing", key_a == key_a, "sink", True) == "sink"
    # Pausing behaves as native even when the track was marked.
    assert menu.volume_mode_for("auto", "paused", True, "sink", True) == "player"
    assert menu.volume_mode_for("auto", "playing", True, "hide", True) == "hidden"


def test_volume_check_marks_only_for_playing_clear_result():
    assert menu.volume_check_marks("playing", True, 1.0, 0.3)
    assert not menu.volume_check_marks("paused", True, 1.0, 0.3)
    assert not menu.volume_check_marks("playing", False, 1.0, 0.3)
    assert not menu.volume_check_marks("playing", True, None, 0.3)
    assert not menu.volume_check_marks("playing", True, 0.3, 0.3)


class FakePlayer:
    base_name = "chromium"
    status = "playing"
    volume = 0.5
    shuffle = False
    can_next = True
    can_previous = True
    can_pause = True
    can_control = True

    def __init__(self, track, loop=None, shuffle=False):
        self.track = track
        self.loop = loop
        self.shuffle = shuffle

    def title(self):
        return "Title " + self.track

    def artist(self):
        return "Artist"

    def album(self):
        return "Album"

    def art_url(self):
        return ""

    def track_id(self):
        return "track-" + self.track

    def track_url(self):
        return "https://example/" + self.track

    def length(self):
        return 100.0


def test_mode_visibility_rechecks_each_session():
    state_a = menu.state_from_player(FakePlayer("A", "track"))
    assert state_a["mode_key"] == "chromium|track-A"
    assert menu.mode_visibility(state_a["shuffle"], state_a["loop"]) == (True, True)

    state_b = menu.state_from_player(FakePlayer("B", None, None))
    assert state_b["mode_key"] == "chromium|track-B"
    assert menu.mode_visibility(state_b["shuffle"], state_b["loop"]) == (False, False)

    state_a2 = menu.state_from_player(FakePlayer("A", "track"))
    assert state_a2["mode_key"] == "chromium|track-A"
    assert menu.mode_visibility(state_a2["shuffle"], state_a2["loop"]) == (True, True)


def test_loop_support_queries_only_selected_player():
    state = menu.state_from_player(FakePlayer("A", None, None))
    assert state["loop"] is None
    assert menu.mode_visibility(state["shuffle"], state["loop"]) == (False, False)


def test_popup_show_defers_slow_work(monkeypatch):
    class FakeCard:
        def set_opacity(self, _value):
            pass

        def set_margin_top(self, _value):
            pass

    class FakeWin:
        def __init__(self):
            self.order = []

        def show_all(self):
            self.order.append("show_all")

    popup = object.__new__(menu.PlayerPopup)
    popup.alive = False
    popup.visible = False
    popup.seed_loaded = True
    popup.anim_from = 0
    popup.anim_id = 0
    popup.refresh_id = 0
    popup.card = FakeCard()
    popup.win = FakeWin()
    popup.animate_open = lambda: False
    popup._after_show = lambda: False
    idle_calls = []
    timers = []
    monkeypatch.setattr(menu.GLib, "idle_add", lambda cb: idle_calls.append(cb) or 1)
    monkeypatch.setattr(menu.GLib, "timeout_add", lambda _ms, cb: timers.append(cb) or 1)
    monkeypatch.setattr(menu, "HAVE_LAYER", False)
    popup.show()
    assert popup.win.order == ["show_all"]
    assert idle_calls == [popup._after_show]
    assert popup._refresh_tick in timers
    assert popup.visible is True
