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
