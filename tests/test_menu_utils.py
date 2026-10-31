import base64
import os
import shutil
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
