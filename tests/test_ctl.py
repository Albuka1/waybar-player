import subprocess

import gi

gi.require_version("Gio", "2.0")
from gi.repository import GLib  # noqa: E402

from helpers import load_module

ctl = load_module("waybar_player_ctl", "bin/waybar-player-ctl")


class FakePlayer:
    volume = 0.50
    shuffle = False
    loop = "none"
    can_control = True

    def __init__(self):
        self.calls = []

    def play_pause(self):
        self.calls.append(("play-pause",))

    def previous(self):
        self.calls.append(("previous",))

    def next(self):
        self.calls.append(("next",))

    def set_property(self, key, value):
        self.calls.append(("set", key, value.unpack()))


def test_ctl_play_pause_uses_player():
    player = FakePlayer()
    assert ctl.dispatch("play-pause", player)
    assert player.calls == [("play-pause",)]


def test_ctl_volume_and_loop_use_properties():
    player = FakePlayer()
    assert ctl.dispatch("volume-up", player)
    assert player.calls[-1][0:2] == ("set", "Volume")
    assert player.calls[-1][2] == 0.55

    assert ctl.dispatch("loop", player)
    assert player.calls[-1] == ("set", "LoopStatus", "Track")


def test_ctl_unavailable_properties_return_false():
    player = FakePlayer()
    player.shuffle = None
    player.loop = None
    assert not ctl.dispatch("shuffle", player)
    assert not ctl.dispatch("loop", player)
