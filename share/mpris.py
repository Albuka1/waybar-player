"""Async MPRIS client built on Gio D-Bus proxies."""

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
PLAYER_IFACE = "org.mpris.MediaPlayer2.Player"
ROOT_IFACE = "org.mpris.MediaPlayer2"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
OBJECT_PATH = "/org/mpris/MediaPlayer2"
TIMEOUT_MS = 500


def _unpack(value):
    if isinstance(value, GLib.Variant):
        return value.unpack()
    return value


class MprisPlayer:
    def __init__(self, manager, name):
        self.manager = manager
        self.name = name
        self.base_name = name[len(MPRIS_PREFIX):].split(".")[0]
        self.status = "stopped"
        self.metadata = {}
        self.volume = None
        self.shuffle = None
        self.loop = None
        self.can_next = False
        self.can_previous = False
        self.can_pause = False
        self.can_control = False
        self.identity = ""
        self.desktop_entry = ""
        self.player_proxy = None
        self.root_proxy = None
        self.ready = False

    def start(self, callback):
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            self.name,
            OBJECT_PATH,
            PLAYER_IFACE,
            None,
            self._player_ready,
            callback,
        )

    def _player_ready(self, _source, result, callback):
        try:
            self.player_proxy = Gio.DBusProxy.new_for_bus_finish(result)
        except GLib.Error:
            callback(self, False)
            return
        self.player_proxy.connect("g-properties-changed", self._properties_changed)
        self._read_player_cache()
        Gio.DBusProxy.new_for_bus(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            self.name,
            OBJECT_PATH,
            ROOT_IFACE,
            None,
            self._root_ready,
            callback,
        )

    def _root_ready(self, _source, result, callback):
        try:
            self.root_proxy = Gio.DBusProxy.new_for_bus_finish(result)
        except GLib.Error:
            self.root_proxy = None
        if self.root_proxy is not None:
            self.root_proxy.connect("g-properties-changed", self._properties_changed)
            self._read_root_cache()
        self.ready = True
        callback(self, True)

    def _properties_changed(self, _proxy, _changed, _invalidated):
        self._read_player_cache()
        self._read_root_cache()
        self.manager.player_changed(self)

    def _apply_player_properties(self, values):
        if "PlaybackStatus" in values:
            self.status = str(values["PlaybackStatus"]).lower()
        if "Metadata" in values:
            data = _unpack(values["Metadata"]) or {}
            self.metadata = {
                str(key): _unpack(value) for key, value in data.items()
            }
        if "Volume" in values:
            self.volume = float(values["Volume"])
        if "Shuffle" in values:
            self.shuffle = bool(values["Shuffle"])
        if "LoopStatus" in values:
            self.loop = str(values["LoopStatus"]).lower()
        for attr, prop in (
            ("can_next", "CanGoNext"),
            ("can_previous", "CanGoPrevious"),
            ("can_pause", "CanPause"),
            ("can_control", "CanControl"),
        ):
            if prop in values:
                setattr(self, attr, bool(values[prop]))

    def _apply_root_properties(self, values):
        if "Identity" in values:
            self.identity = str(values["Identity"])
        if "DesktopEntry" in values:
            self.desktop_entry = str(values["DesktopEntry"])

    def _read_player_cache(self):
        proxy = self.player_proxy
        if proxy is None:
            return
        cached = {}
        for prop in (
            "PlaybackStatus", "Metadata", "Volume", "Shuffle", "LoopStatus",
            "CanGoNext", "CanGoPrevious", "CanPause", "CanControl",
        ):
            value = proxy.get_cached_property(prop)
            if value is not None:
                cached[prop] = value.unpack()
        self._apply_player_properties(cached)

    def _read_root_cache(self):
        proxy = self.root_proxy
        if proxy is None:
            return
        cached = {}
        for prop in ("Identity", "DesktopEntry"):
            value = proxy.get_cached_property(prop)
            if value is not None:
                cached[prop] = value.unpack()
        self._apply_root_properties(cached)

    def _metadata_value(self, key, default=""):
        value = self.metadata.get(key, default)
        value = _unpack(value)
        if isinstance(value, list):
            return "; ".join(str(item) for item in value)
        return "" if value is None else str(value)

    def title(self):
        return self._metadata_value("xesam:title")

    def artist(self):
        return self._metadata_value("xesam:artist")

    def album(self):
        return self._metadata_value("xesam:album")

    def art_url(self):
        return self._metadata_value("mpris:artUrl")

    def track_id(self):
        return self._metadata_value("mpris:trackid")

    def track_url(self):
        return self._metadata_value("xesam:url")

    def length(self):
        value = self.metadata.get("mpris:length")
        try:
            return float(value) / 1_000_000.0 if value is not None else None
        except (TypeError, ValueError):
            return None

    def _call(self, method, params=None, callback=None):
        if self.player_proxy is None:
            if callback:
                callback(None, None)
            return
        self.player_proxy.call(
            method,
            params,
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._call_done,
            callback,
        )

    def _call_done(self, proxy, result, callback):
        value = None
        try:
            reply = proxy.call_finish(result)
            if reply is not None:
                value = reply.unpack()
        except GLib.Error:
            value = None
        if callback:
            callback(value, None)

    def play_pause(self, callback=None):
        self._call("PlayPause", None, callback)

    def next(self, callback=None):
        self._call("Next", None, callback)

    def previous(self, callback=None):
        self._call("Previous", None, callback)

    def set_property(self, key, variant, callback=None):
        if self.player_proxy is None:
            if callback:
                callback(None, None)
            return
        connection = self.player_proxy.get_connection()
        connection.call(
            self.name,
            OBJECT_PATH,
            PROPS_IFACE,
            "Set",
            GLib.Variant("(ssv)", (PLAYER_IFACE, key, variant)),
            None,
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._call_done,
            callback,
        )

    def get_property(self, key, callback=None):
        if self.player_proxy is None:
            if callback:
                callback(None, None)
            return
        connection = self.player_proxy.get_connection()
        connection.call(
            self.name,
            OBJECT_PATH,
            PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (PLAYER_IFACE, key)),
            GLib.VariantType.new("(v)"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._get_property_done,
            callback,
        )

    def _get_property_done(self, _connection, result, callback):
        value = None
        try:
            reply = _connection.call_finish(result)
            value = reply.unpack()[0]
            value = _unpack(value)
        except (GLib.Error, TypeError, IndexError):
            value = None
        if callback:
            callback(value, None)

    def get_position(self, callback=None):
        if self.player_proxy is None:
            if callback:
                callback(None, None)
            return
        connection = self.player_proxy.get_connection()
        connection.call(
            self.name,
            OBJECT_PATH,
            PROPS_IFACE,
            "Get",
            GLib.Variant("(ss)", (PLAYER_IFACE, "Position")),
            GLib.VariantType.new("(v)"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._position_done,
            callback,
        )

    def _position_done(self, _connection, result, callback):
        value = None
        try:
            reply = _connection.call_finish(result)
            value = _unpack(reply.unpack()[0])
        except (GLib.Error, TypeError, IndexError):
            value = None
        if callback:
            callback(value, None)

    def seek(self, offset_us, callback=None):
        self._call("Seek", GLib.Variant("(x)", (int(offset_us),)), callback)

    def set_position(self, track_id, position_us, callback=None):
        self._call(
            "SetPosition",
            GLib.Variant("(ox)", (track_id, int(position_us))),
            callback,
        )

    def refresh(self, callback=None):
        if self.player_proxy is None:
            if callback:
                callback()
            return
        connection = self.player_proxy.get_connection()
        connection.call(
            self.name,
            OBJECT_PATH,
            PROPS_IFACE,
            "GetAll",
            GLib.Variant("(s)", (PLAYER_IFACE,)),
            GLib.VariantType.new("(a{sv})"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._get_all_done,
            callback,
        )
        connection.call(
            self.name,
            OBJECT_PATH,
            PROPS_IFACE,
            "GetAll",
            GLib.Variant("(s)", (ROOT_IFACE,)),
            GLib.VariantType.new("(a{sv})"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._get_root_all_done,
            None,
        )

    def _get_root_all_done(self, connection, result, _callback):
        try:
            values = connection.call_finish(result).unpack()[0]
            self._apply_root_properties(values)
        except (GLib.Error, TypeError, IndexError):
            pass

    def _get_all_done(self, connection, result, callback):
        try:
            reply = connection.call_finish(result)
            values = reply.unpack()[0]
            self._apply_player_properties(values)
        except (GLib.Error, TypeError, IndexError):
            pass
        if callback:
            callback()


class MprisManager:
    def __init__(self, on_change=None):
        self.on_change = on_change or (lambda: None)
        self.players = {}
        self.bus = None
        self._started = False
        self._ready = None
        self._pending = 0
        self._names_done = False

    def start(self, ready=None):
        self._ready = ready
        Gio.bus_get(Gio.BusType.SESSION, None, self._bus_ready)

    def _bus_ready(self, _source, result):
        try:
            self.bus = Gio.bus_get_finish(result)
        except GLib.Error:
            self.on_change()
            return
        self.bus.signal_subscribe(
            "org.freedesktop.DBus",
            "org.freedesktop.DBus",
            "NameOwnerChanged",
            "/org/freedesktop/DBus",
            None,
            Gio.DBusSignalFlags.NONE,
            self._name_owner_changed,
        )
        self.bus.call(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "ListNames",
            None,
            GLib.VariantType.new("(as)"),
            Gio.DBusCallFlags.NONE,
            TIMEOUT_MS,
            None,
            self._names_ready,
        )

    def _names_ready(self, _connection, result):
        try:
            names = _connection.call_finish(result).unpack()[0]
        except (GLib.Error, TypeError, IndexError):
            names = []
        for name in names:
            if name.startswith(MPRIS_PREFIX):
                self._add(name)
        self._names_done = True
        self._maybe_ready()

    def _maybe_ready(self):
        if self._names_done and self._pending == 0 and self._ready:
            callback = self._ready
            self._ready = None
            callback()

    def _name_owner_changed(self, _connection, _sender, _path, _iface, _signal, params):
        name, _old, new = params.unpack()
        if not name.startswith(MPRIS_PREFIX):
            return
        if new:
            if name not in self.players:
                self._add(name)
        else:
            self.players.pop(name, None)
            self.on_change()

    def _add(self, name):
        player = MprisPlayer(self, name)
        self.players[name] = player
        self._pending += 1

        def ready(_player, _ok):
            self._pending = max(0, self._pending - 1)
            self.on_change()
            self._maybe_ready()

        player.start(ready)

    def player_changed(self, _player):
        self.on_change()

    def refresh_all(self, callback=None):
        players = list(self.players.values())
        if not players:
            if callback:
                callback()
            return
        remaining = [len(players)]

        def done():
            remaining[0] -= 1
            if remaining[0] == 0 and callback:
                callback()

        for player in players:
            player.refresh(done)
