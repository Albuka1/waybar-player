#!/usr/bin/env python3
"""Minimal fake MPRIS service for tests (private session bus)."""

import os
import sys

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

NAME = "org.mpris.MediaPlayer2.fake"
PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
STATE = os.environ["FAKE_MPRIS_STATE"]

XML = """
<node>
  <interface name="org.mpris.MediaPlayer2.Player">
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Shuffle" type="b" access="readwrite"/>
    <property name="LoopStatus" type="s" access="readwrite"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
    <method name="PlayPause"/>
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Seek"><arg direction="in" type="x"/></method>
    <method name="SetPosition"><arg direction="in" type="o"/><arg direction="in" type="x"/></method>
  </interface>
</node>
"""


def read_state():
    with open(STATE, encoding="utf-8") as handle:
        return handle.read().strip() or "Playing"


def metadata(status):
    return {
        "xesam:title": GLib.Variant("s", "Fake title"),
        "xesam:artist": GLib.Variant("as", ["Fake artist"]),
        "xesam:album": GLib.Variant("s", "Fake album"),
        "mpris:trackid": GLib.Variant("o", "/fake/track/1"),
        "xesam:url": GLib.Variant("s", "https://example/track"),
        "mpris:artUrl": GLib.Variant("s", ""),
        "mpris:length": GLib.Variant("x", 120_000_000),
    }


def main():
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    info = Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0]
    state = {"value": read_state(), "volume": 0.5, "shuffle": False, "loop": "None"}

    def get_property(_conn, _sender, _path, _iface, prop):
        if prop == "PlaybackStatus":
            return GLib.Variant("s", state["value"])
        if prop == "Metadata":
            return GLib.Variant("a{sv}", metadata(state["value"]))
        if prop == "Volume":
            return GLib.Variant("d", state["volume"])
        if prop == "Shuffle":
            return GLib.Variant("b", state["shuffle"])
        if prop == "LoopStatus":
            return GLib.Variant("s", state["loop"])
        if prop in ("CanGoNext", "CanGoPrevious", "CanPause", "CanControl"):
            return GLib.Variant("b", True)
        return None

    def set_property(_conn, _sender, _path, _iface, prop, value):
        if prop == "Volume":
            state["volume"] = float(value.unpack())
        elif prop == "Shuffle":
            state["shuffle"] = bool(value.unpack())
        elif prop == "LoopStatus":
            state["loop"] = str(value.unpack())
        return True

    def method(_conn, _sender, _path, _iface, name, _params, invocation):
        if name == "PlayPause":
            state["value"] = "Paused" if state["value"] == "Playing" else "Playing"
        invocation.return_value(None)

    connection.register_object(PATH, info, method, get_property, set_property)
    Gio.bus_own_name_on_connection(
        connection, NAME, Gio.BusNameOwnerFlags.NONE, None, None
    )
    last = {"value": state["value"]}

    def tick():
        current = read_state()
        if current != last["value"]:
            last["value"] = current
            state["value"] = current
            changed = {
                "PlaybackStatus": GLib.Variant("s", current),
                "Metadata": GLib.Variant("a{sv}", metadata(current)),
            }
            connection.emit_signal(
                None, PATH, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (PLAYER, changed, [])),
            )
        return True

    GLib.timeout_add(50, tick)
    GLib.MainLoop().run()


if __name__ == "__main__":
    sys.exit(main())
