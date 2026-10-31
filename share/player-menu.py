#!/usr/bin/env python3
import colorsys
import glob
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n import t  # noqa: E402
import players  # noqa: E402

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango", "1.0")

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell  # noqa: E402

    HAVE_LAYER = True
except (ValueError, ImportError):
    GtkLayerShell = None
    HAVE_LAYER = False

SEP = "\x1f"
FMT = SEP.join([
    "{{status}}", "{{playerName}}", "{{title}}", "{{artist}}",
    "{{album}}", "{{mpris:artUrl}}", "{{volume}}",
    "{{position}}", "{{mpris:length}}", "{{mpris:trackid}}", "{{xesam:url}}",
])
CACHE_DIR = os.environ.get("PM_CACHE") or os.path.join(
    os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
    "waybar-player",
)

def env_int(name, default, minimum):
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return max(minimum, value)


WIDTH = env_int("WAYBAR_PLAYER_WIDTH", 320, 200)
CARD_TOP_MARGIN = 8      # зазор карточки от рабочей области под Waybar
RIGHT_MARGIN = env_int("WAYBAR_PLAYER_RIGHT_MARGIN", 215, 0)
COVER_SIZE = 72
DEFAULT_ACCENT = "#ff8c00"
ACCENT_MODE = os.environ.get("WAYBAR_PLAYER_ACCENT", "cover").strip().lower()
if ACCENT_MODE not in ("cover", "fixed"):
    ACCENT_MODE = "cover"
VOLUME_MODE = os.environ.get("WAYBAR_PLAYER_VOLUME_MODE", "auto").strip().lower()
if VOLUME_MODE not in ("auto", "player", "sink", "hide"):
    VOLUME_MODE = "auto"
VOLUME_FALLBACK = os.environ.get("WAYBAR_PLAYER_VOLUME_FALLBACK", "sink").strip().lower()
if VOLUME_FALLBACK not in ("sink", "hide"):
    VOLUME_FALLBACK = "sink"
HAVE_WPCTL = shutil.which("wpctl") is not None
PLAYERCTL_TIMEOUT = 1.5
OPEN_ANIM_MS = 100
ART_MAX_BYTES = 8 * 1024 * 1024
ART_TIMEOUT = 4
CACHE_MAX_AGE_DAYS = 14

CSS = b"""
* {
    font-family: "JetBrainsMono Nerd Font", sans-serif;
}
window {
    background-color: transparent;
    background-image: none;
}
#backdrop {
    background-color: rgba(0, 0, 0, 0.18);
}
#player-card {
    background-color: #0d0d0d;
    border: 1px solid #2a2a2a;
    border-top: 2px solid #ff8c00;
    border-radius: 12px;
    padding: 14px;
}
#popup-title {
    color: #ff8c00;
    font-size: 14px;
    font-weight: 700;
}
#popup-artist {
    color: #cfcfcf;
    font-size: 11px;
}
#popup-album {
    color: #777777;
    font-size: 9px;
}
#time-label {
    color: #888888;
    font-size: 9px;
}
#popup-small {
    color: #aaaaaa;
    font-size: 10px;
}
button {
    background-image: none;
    background-color: transparent;
    border: none;
    box-shadow: none;
    text-shadow: none;
    color: #e0e0e0;
}
button:hover {
    background-color: rgba(255, 140, 0, 0.18);
    color: #ff8c00;
}
button:active {
    background-color: #ff8c00;
    color: #0d0d0d;
}
button:disabled {
    color: #555555;
}
#close-btn {
    color: #777777;
    font-size: 11px;
    padding: 0;
}
#close-btn:hover {
    background-color: #cc0000;
    color: #ffffff;
}
.control-btn {
    font-size: 28px;
    padding: 3px 8px;
    border-radius: 8px;
}
#play-btn {
    background-color: #1a1a1a;
    border-radius: 50%;
    font-size: 24px;
    padding: 5px 12px;
}
#play-btn:hover {
    background-color: #ff8c00;
    color: #0d0d0d;
}
.mode-btn {
    font-size: 18px;
    padding: 2px 0;
    border-radius: 6px;
}
.mode-btn.active {
    color: #ff8c00;
}
.icon-btn {
    font-size: 14px;
    padding: 0 4px;
}
scale trough {
    background-image: none;
    background-color: #2a2a2a;
    border-radius: 2px;
    min-height: 4px;
}
scale trough highlight {
    background-image: none;
    background-color: #ff8c00;
    border-radius: 2px;
}
scale trough slider {
    background-image: none;
    background-color: #ff8c00;
    border: none;
    border-radius: 50%;
    box-shadow: none;
    min-width: 10px;
    min-height: 10px;
}
#volume-scale trough {
    min-height: 6px;
}
#volume-scale trough slider {
    min-width: 12px;
    min-height: 12px;
}
scale:disabled trough {
    background-color: #1f1f1f;
}
scale:disabled trough highlight {
    background-color: #333333;
}
scale:disabled trough slider {
    background-color: #444444;
}
"""


def pctl(*args, player=None, timeout=PLAYERCTL_TIMEOUT):
    """playerctl с жёстким таймаутом и обязательным -p."""
    if not player:
        return None
    try:
        return subprocess.run(
            ["playerctl", "-p", player, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def to_seconds(raw):
    """playerctl отдаёт position/length в микросекундах."""
    if not raw:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0:
        value = 0.0
    return value / 1_000_000.0


def fmt_time(seconds):
    if seconds is None:
        return "0:00"
    try:
        total = int(max(0, float(seconds)))
    except (TypeError, ValueError):
        return "0:00"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def volume_icon(pct):
    if pct <= 0:
        return "󰝟"
    if pct < 34:
        return "󰕿"
    if pct < 67:
        return "󰖀"
    return "󰕾"


def get_state(player):
    if not player:
        return None
    res = pctl("metadata", "--format", FMT, player=player)
    if res is None or res.returncode != 0:
        return None
    line = res.stdout.rstrip("\n")
    if not line:
        return None

    parts = line.split(SEP)
    if len(parts) < 11:
        parts += [""] * (11 - len(parts))

    (status, player, title, artist, album, art_url, vol_raw, pos_raw,
     len_raw, track_id, track_url) = parts[:11]
    try:
        volume = max(0.0, min(1.0, float(vol_raw))) if vol_raw else None
    except (TypeError, ValueError):
        volume = None

    length = to_seconds(len_raw)
    if length is not None and length <= 0:
        length = None

    state = {
        "status": status.strip().lower(),
        "player": player.strip(),
        "title": title,
        "artist": artist,
        "album": album,
        "art_url": art_url,
        "volume": volume,
        "position": to_seconds(pos_raw) or 0.0,
        "length": length,
        "shuffle": parse_shuffle(_read_mode("shuffle", player)),
        "loop": parse_loop(_read_mode("loop", player)),
        "track_id": track_id,
        "track_url": track_url,
    }
    state["mode_key"] = volume_track_key(state)
    return state


def parse_shuffle(value):
    text = (value or "").strip().lower()
    if text in ("on", "off"):
        return text
    return None


def parse_loop(value):
    text = (value or "").strip().lower()
    if text in ("none", "track", "playlist"):
        return text
    return None


def mode_visibility(shuffle, loop):
    return (shuffle is not None, loop is not None)


def next_loop(value):
    return {"none": "track", "track": "playlist", "playlist": "none"}.get(value)


def loop_command(value):
    return {"none": "None", "track": "Track", "playlist": "Playlist"}.get(value)


def _read_mode(command, player):
    res = pctl(command, player=player)
    if res is None or res.returncode != 0:
        return None
    return res.stdout.strip()


def cleanup_cover_cache(max_age_days=CACHE_MAX_AGE_DAYS):
    """Удаляет popup-*.img, которые не использовались дольше max_age_days."""
    cutoff = time.time() - max_age_days * 24 * 60 * 60
    for path in glob.glob(os.path.join(CACHE_DIR, "popup-*.img")):
        try:
            if os.path.getmtime(path) < cutoff:
                os.unlink(path)
        except OSError:
            continue


def _is_public_address(host):
    """True, если ВСЕ адреса хоста публичные (защита от SSRF)."""
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not address.is_global:
            return False
        if (address.is_private or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_reserved
                or address.is_unspecified):
            return False
    return True


def validate_art_url(url):
    """Разрешает только https-URL с публичным хостом."""
    if not url or not isinstance(url, str):
        return False
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parts.scheme != "https":
        return False
    if not parts.hostname:
        return False
    if parts.username or parts.password:
        return False
    return _is_public_address(parts.hostname)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        absolute = urllib.parse.urljoin(req.full_url, newurl)
        if not validate_art_url(absolute):
            raise urllib.error.HTTPError(
                absolute, code, "blocked redirect to non-public URL", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, absolute)


_ART_OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    _SafeRedirectHandler(),
)


def _allowed_art_roots():
    roots = ["/tmp"]
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        roots.append(runtime)
    roots.append(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"))
    extra = os.environ.get("WAYBAR_PLAYER_ART_DIRS", "")
    roots.extend(part for part in extra.split(os.pathsep) if part)
    resolved = []
    for root in roots:
        try:
            resolved.append(os.path.realpath(os.path.expanduser(root)))
        except OSError:
            continue
    return resolved


def _has_image_signature(path):
    try:
        with open(path, "rb") as handle:
            head = handle.read(16)
    except OSError:
        return False
    return (
        head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith((b"GIF87a", b"GIF89a"))
        or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def validate_file_art_url(url):
    """file:// разрешён только для обычных картинок внутри белого списка."""
    if not url or not isinstance(url, str):
        return None
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() != "file":
        return None
    if (parts.hostname or "").lower() not in ("", "localhost"):
        return None

    path = urllib.parse.unquote(parts.path)
    if not path or not os.path.isabs(path):
        return None
    try:
        real = os.path.realpath(path)
        st = os.stat(real)
    except OSError:
        return None
    if not os.path.isfile(real) or not (0 < st.st_size <= ART_MAX_BYTES):
        return None
    if not any(real.startswith(root + os.sep) for root in _allowed_art_roots()):
        return None
    if not _has_image_signature(real):
        return None
    return real


def fetch_art(url):
    """Скачивает https-обложку или отдаёт проверенный локальный file:// путь."""
    if not url or not isinstance(url, str):
        return None
    try:
        scheme = urllib.parse.urlsplit(url).scheme.lower()
    except ValueError:
        return None
    if scheme == "file":
        return validate_file_art_url(url)
    if not validate_art_url(url):
        return None
    try:
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        dest = os.path.join(CACHE_DIR, "popup-" + key + ".img")
        if os.path.isfile(dest) and os.path.getsize(dest) > 0:
            return dest

        req = urllib.request.Request(url, headers={"User-Agent": "waybar-player/1.0"})
        with _ART_OPENER.open(req, timeout=ART_TIMEOUT) as resp:
            final_url = resp.geturl()
            if not validate_art_url(final_url):
                return None
            data = resp.read(ART_MAX_BYTES + 1)
        if not data or len(data) > ART_MAX_BYTES:
            return None

        tmp = dest + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, dest)
        return dest
    except Exception:
        return None


def load_cover(path):
    if not path:
        return None
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
    except GLib.Error:
        return None
    w, h = pb.get_width(), pb.get_height()
    if w <= 0 or h <= 0:
        return None
    if w > COVER_SIZE or h > COVER_SIZE:
        ratio = min(COVER_SIZE / w, COVER_SIZE / h)
        pb = pb.scale_simple(
            max(1, int(w * ratio)), max(1, int(h * ratio)),
            GdkPixbuf.InterpType.BILINEAR,
        )
    return pb


def parse_wpctl_volume(text):
    if not text:
        return None
    match = re.search(r"Volume:\s*([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    try:
        return max(0.0, min(1.0, float(match.group(1))))
    except ValueError:
        return None


def volume_readback_matches(actual, target, tolerance=0.03):
    return actual is not None and abs(actual - target) <= tolerance


def volume_track_key(state):
    player = state.get("player") or ""
    track = (
        state.get("track_id")
        or state.get("track_url")
        or "{}|{}".format(state.get("title") or "", state.get("artist") or "")
    )
    return "{}|{}".format(player, track)


def volume_check_marks(status, set_ok, read_value, target, tolerance=0.03):
    if status != "playing" or not set_ok or read_value is None:
        return False
    return not volume_readback_matches(read_value, target, tolerance)


def volume_mode_for(mode, status, marked, fallback=None, have_wpctl=None):
    if mode == "player":
        return "player"
    if mode == "sink":
        have_wpctl = HAVE_WPCTL if have_wpctl is None else have_wpctl
        return "sink" if have_wpctl else "hidden"
    if mode == "hide":
        return "hidden"
    # auto: native unless the current playing track is known to ignore volume.
    if status != "playing" or not marked:
        return "player"
    fallback = VOLUME_FALLBACK if fallback is None else fallback
    have_wpctl = HAVE_WPCTL if have_wpctl is None else have_wpctl
    return "sink" if fallback == "sink" and have_wpctl else "hidden"


def wpctl_get_volume():
    if not HAVE_WPCTL:
        return None
    try:
        result = subprocess.run(
            ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return parse_wpctl_volume(result.stdout)


def wpctl_set_volume(value):
    if not HAVE_WPCTL:
        return False
    try:
        result = subprocess.run(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "{:.2f}".format(value)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _hex_rgb(color):
    value = color.lstrip("#")
    if len(value) != 6:
        return (255, 140, 0)
    try:
        return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return (255, 140, 0)


def accent_foreground(color):
    """Чёрный или белый значок по контрасту с акцентным фоном."""
    red, green, blue = _hex_rgb(color)

    def linear(channel):
        channel = channel / 255.0
        if channel <= 0.03928:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    luminance = (
        0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue)
    )
    black_contrast = (luminance + 0.05) / 0.05
    white_contrast = 1.05 / (luminance + 0.05)
    return "#000000" if black_contrast >= white_contrast else "#ffffff"


def accent_soft(color, alpha=0.18):
    red, green, blue = _hex_rgb(color)
    return "rgba({}, {}, {}, {})".format(red, green, blue, alpha)


def readable_accent(r, g, b):
    """Поднимает светлоту и насыщенность цвета до читаемого порога."""
    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    lightness = max(lightness, 0.60)
    saturation = max(saturation, 0.55)
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return "#{:02x}{:02x}{:02x}".format(
        int(round(red * 255)), int(round(green * 255)), int(round(blue * 255))
    )


def pixbuf_accent(pixbuf):
    try:
        small = pixbuf.scale_simple(1, 1, GdkPixbuf.InterpType.BILINEAR)
        pixels = small.get_pixels()
        return readable_accent(pixels[0], pixels[1], pixels[2])
    except (GLib.Error, TypeError, IndexError):
        return DEFAULT_ACCENT


class PlayerPopup:
    def __init__(self):
        self.state = None
        self.art_url = None
        self.art_token = 0
        self.length = None
        self.alive = True

        self.vol_timeout = 0
        self.vol_dragging = False
        self.updating_vol = False
        self.volume_readback_id = 0
        self.volume_key = None
        self.volume_ineffective_key = None
        self.mode_key = None
        self.volume_mode = "player"
        self.player = ""
        self.selected = None

        self.seek_timeout = 0
        self.seek_dragging = False
        self.updating_seek = False
        self.last_seek = 0.0

        self.refresh_id = 0
        self.anim_id = 0
        self.fade_id = 0
        self.ws_timer = 0
        self.workspace_id = None
        self.anim_start = 0.0
        self.anim_from = 0
        self.fade_id = 0
        self.fade_step = 0
        self.last_track_key = None

        self.win = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.win.set_title(t("menu.title"))
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        self.win.set_skip_taskbar_hint(True)
        self.win.set_skip_pager_hint(True)
        self.win.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.win.set_app_paintable(True)

        screen = self.win.get_screen()
        self.screen = screen
        self.accent_provider = Gtk.CssProvider()
        if screen is not None:
            Gtk.StyleContext.add_provider_for_screen(
                screen,
                self.accent_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1,
            )
        self.apply_accent(DEFAULT_ACCENT)

        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None:
            self.win.set_visual(visual)

        if HAVE_LAYER:
            GtkLayerShell.init_for_window(self.win)
            GtkLayerShell.set_namespace(self.win, "waybar-player")
            GtkLayerShell.set_layer(self.win, GtkLayerShell.Layer.OVERLAY)
            # Полноэкранная прозрачная поверхность: карточка позиционируется
            # внутри неё, а затемнение ловит клики вне карточки.
            for edge in (
                GtkLayerShell.Edge.TOP,
                GtkLayerShell.Edge.BOTTOM,
                GtkLayerShell.Edge.LEFT,
                GtkLayerShell.Edge.RIGHT,
            ):
                GtkLayerShell.set_anchor(self.win, edge, True)
                GtkLayerShell.set_margin(self.win, edge, 0)
            GtkLayerShell.set_exclusive_zone(self.win, 0)
            GtkLayerShell.set_keyboard_mode(
                self.win, GtkLayerShell.KeyboardMode.ON_DEMAND
            )
        else:
            self.win.set_keep_above(True)
            self.win.set_position(Gtk.WindowPosition.CENTER)
            self.win.set_size_request(WIDTH, -1)

        self.win.connect("destroy", self.on_destroy)
        self.win.connect("key-press-event", self.on_key)
        self.win.connect("button-press-event", self.on_pointer_click)

        self.card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.card.set_name("player-card")

        # --- шапка: обложка, текст, закрыть ---------------------------------
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self.cover = Gtk.Image()
        self.cover.set_size_request(COVER_SIZE, COVER_SIZE)
        self.cover.set_halign(Gtk.Align.CENTER)
        self.cover.set_valign(Gtk.Align.CENTER)
        header.pack_start(self.cover, False, False, 0)

        textbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        textbox.set_valign(Gtk.Align.CENTER)
        textbox.set_hexpand(True)

        self.title_label = Gtk.Label()
        self.title_label.set_name("popup-title")
        self.title_label.set_xalign(0.0)
        self.title_label.set_single_line_mode(True)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(22)
        textbox.pack_start(self.title_label, False, False, 0)

        self.artist_label = Gtk.Label()
        self.artist_label.set_name("popup-artist")
        self.artist_label.set_xalign(0.0)
        self.artist_label.set_single_line_mode(True)
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_max_width_chars(26)
        textbox.pack_start(self.artist_label, False, False, 0)

        self.album_label = Gtk.Label()
        self.album_label.set_name("popup-album")
        self.album_label.set_xalign(0.0)
        self.album_label.set_single_line_mode(True)
        self.album_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.album_label.set_max_width_chars(28)
        textbox.pack_start(self.album_label, False, False, 0)

        header.pack_start(textbox, True, True, 0)

        self.close_btn = Gtk.Button(label="✕")
        self.close_btn.set_name("close-btn")
        self.close_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.close_btn.set_size_request(22, 22)
        self.close_btn.set_valign(Gtk.Align.START)
        self.close_btn.set_tooltip_text(t("menu.close"))
        self.close_btn.connect("clicked", self.close)
        header.pack_end(self.close_btn, False, False, 0)

        self.card.pack_start(header, False, False, 0)

        # --- кнопки управления ----------------------------------------------
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls.set_halign(Gtk.Align.CENTER)

        self.prev_btn = self._control("󰒮", t("menu.prev"), self.on_prev)
        self.play_btn = self._control("󰐊", t("menu.play_pause"), self.on_play_pause)
        self.next_btn = self._control("󰒭", t("menu.next"), self.on_next)
        self.shuffle_btn = self._control("󰒝", t("menu.shuffle"), self.on_shuffle)
        self.loop_btn = self._control("󰑖", t("menu.loop"), self.on_loop)
        self.play_btn.set_name("play-btn")
        self.prev_btn.set_size_request(52, 46)
        self.play_btn.set_size_request(56, 56)
        self.next_btn.set_size_request(52, 46)
        for btn in (self.shuffle_btn, self.loop_btn):
            btn.get_style_context().add_class("mode-btn")
            btn.set_size_request(30, 46)
            btn.set_no_show_all(True)
            btn.hide()

        for btn in (self.shuffle_btn, self.prev_btn, self.play_btn,
                    self.next_btn, self.loop_btn):
            controls.pack_start(btn, False, False, 0)

        self.card.pack_start(controls, False, False, 0)

        # --- нижняя зона: статус/громкость (одна высота, без ресайза) --------
        self.info_stack = Gtk.Stack()
        self.info_stack.set_size_request(-1, 24)
        self.info_stack.set_hhomogeneous(True)
        self.info_stack.set_vhomogeneous(True)

        status_page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_name("popup-small")
        self.status_label.set_xalign(0.0)
        self.status_label.set_valign(Gtk.Align.CENTER)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        status_page.pack_start(self.status_label, True, True, 0)
        self.info_stack.add_named(status_page, "status")

        vol_page = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol_page.set_valign(Gtk.Align.CENTER)

        self.vol_title = Gtk.Label(label=t("menu.volume"))
        self.vol_title.set_name("popup-small")
        self.vol_title.set_xalign(0.0)
        vol_page.pack_start(self.vol_title, False, False, 0)

        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.vol_scale.set_name("volume-scale")
        self.vol_scale.set_draw_value(False)
        self.vol_scale.set_hexpand(True)
        self.vol_scale.set_valign(Gtk.Align.CENTER)
        self.vol_scale.connect("value-changed", self.on_volume_changed)
        self.vol_scale.connect("button-press-event", self.on_volume_press)
        self.vol_scale.connect("button-release-event", self.on_volume_release)
        vol_page.pack_start(self.vol_scale, True, True, 0)

        self.vol_value = Gtk.Label(label="—")
        self.vol_value.set_name("popup-small")
        self.vol_value.set_width_chars(4)
        self.vol_value.set_xalign(1.0)
        vol_page.pack_start(self.vol_value, False, False, 0)

        self.info_stack.add_named(vol_page, "volume")
        self.info_stack.set_visible_child_name("status")
        self.card.pack_start(self.info_stack, False, False, 0)

        # --- перемотка (всегда снизу) ---------------------------------------
        seekrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.vol_btn = Gtk.Button(label="󰕾")
        self.vol_btn.get_style_context().add_class("icon-btn")
        self.vol_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.vol_btn.set_size_request(22, 22)
        self.vol_btn.connect("clicked", self.toggle_volume_page)
        seekrow.pack_start(self.vol_btn, False, False, 0)

        self.cur_label = Gtk.Label(label="0:00")
        self.cur_label.set_name("time-label")
        self.cur_label.set_width_chars(5)
        self.cur_label.set_xalign(1.0)
        seekrow.pack_start(self.cur_label, False, False, 0)

        self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 0.1)
        self.seek.set_name("seek-scale")
        self.seek.set_draw_value(False)
        self.seek.set_hexpand(True)
        self.seek.set_increments(5, 30)
        self.seek.set_sensitive(False)
        self.seek.connect("value-changed", self.on_seek_changed)
        self.seek.connect("button-press-event", self.on_seek_press)
        self.seek.connect("button-release-event", self.on_seek_release)
        seekrow.pack_start(self.seek, True, True, 0)

        self.total_label = Gtk.Label(label="0:00")
        self.total_label.set_name("time-label")
        self.total_label.set_width_chars(5)
        self.total_label.set_xalign(0.0)
        seekrow.pack_start(self.total_label, False, False, 0)

        self.card.pack_start(seekrow, False, False, 0)

        if HAVE_LAYER:
            # Прозрачный полноэкранный слой: клик по затемнению закрывает меню.
            self.backdrop = Gtk.EventBox()
            self.backdrop.set_name("backdrop")
            self.backdrop.set_visible_window(True)
            self.backdrop.connect("button-press-event", self.on_pointer_click)

            overlay = Gtk.Overlay()
            overlay.add(self.backdrop)
            self.card.set_halign(Gtk.Align.END)
            self.card.set_valign(Gtk.Align.START)
            self.card.set_margin_top(CARD_TOP_MARGIN)
            self.card.set_margin_end(RIGHT_MARGIN)
            self.card.set_size_request(WIDTH, -1)
            overlay.add_overlay(self.card)
            self.win.add(overlay)
        else:
            self.card.set_size_request(WIDTH, -1)
            self.win.add(self.card)

        self.set_placeholder()

    def _control(self, label, tooltip, callback):
        btn = Gtk.Button(label=label)
        btn.get_style_context().add_class("control-btn")
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.set_tooltip_text(tooltip)
        btn.connect("clicked", callback)
        return btn

    # --- жизненный цикл -----------------------------------------------------

    def show(self):
        self.anim_from = max(0, CARD_TOP_MARGIN - 10)
        # Сразу показываем карточку полупрозрачной: нет ощущения пустого окна,
        # а короткий fade/слайд только завершает появление.
        self.card.set_opacity(0.30)
        if HAVE_LAYER:
            self.card.set_margin_top(self.anim_from)

        self.win.show_all()
        self.refresh()

        self.anim_start = time.monotonic()
        self.anim_id = GLib.timeout_add(16, self.animate_open)
        self.refresh_id = GLib.timeout_add(1000, self.refresh)

        # Закрываем меню при смене воркспейса. Polling дешевле и надёжнее
        # долгоживущего niri event-stream (его пришлось бы отдельно убивать).
        self.check_workspace()
        self.ws_timer = GLib.timeout_add(500, self.check_workspace)

    def animate_open(self):
        if not self.alive:
            return False
        duration = OPEN_ANIM_MS / 1000.0
        t = min(1.0, (time.monotonic() - self.anim_start) / duration)
        eased = 1.0 - (1.0 - t) ** 3
        self.card.set_opacity(0.30 + 0.70 * eased)
        if HAVE_LAYER:
            top = self.anim_from + (CARD_TOP_MARGIN - self.anim_from) * eased
            self.card.set_margin_top(int(round(top)))
        if t >= 1.0:
            self.card.set_opacity(1.0)
            if HAVE_LAYER:
                self.card.set_margin_top(CARD_TOP_MARGIN)
            self.anim_id = 0
            return False
        return True

    def close(self, *_args):
        self.win.destroy()

    def _focused_workspace_id(self):
        try:
            res = subprocess.run(
                ["niri", "msg", "--json", "workspaces"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=0.6,
            )
            if res.returncode != 0:
                return None
            for ws in json.loads(res.stdout):
                if ws.get("is_focused"):
                    return ws.get("id")
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
        return None

    def check_workspace(self):
        if not self.alive:
            return False
        focused = self._focused_workspace_id()
        if focused is None:
            return True
        if self.workspace_id is None:
            self.workspace_id = focused
        elif focused != self.workspace_id:
            self.close()
            return False
        return True

    def on_pointer_click(self, _widget, event):
        if event.button != 1:
            return False
        alloc = self.card.get_allocation()
        coords = self.card.translate_coordinates(self.win, 0, 0)
        if coords is None:
            cx, cy = alloc.x, alloc.y
        else:
            cx, cy = coords
        inside = (
            cx <= event.x <= cx + alloc.width
            and cy <= event.y <= cy + alloc.height
        )
        if inside:
            return False
        self.close()
        return True

    def on_destroy(self, _widget):
        self.alive = False
        for source in (
            self.refresh_id,
            self.vol_timeout,
            self.volume_readback_id,
            self.seek_timeout,
            self.anim_id,
            self.fade_id,
            self.ws_timer,
        ):
            if source:
                GLib.source_remove(source)
        self.refresh_id = 0
        self.vol_timeout = 0
        self.volume_readback_id = 0
        self.seek_timeout = 0
        self.anim_id = 0
        self.fade_id = 0
        self.ws_timer = 0
        if self.accent_provider is not None and self.screen is not None:
            Gtk.StyleContext.remove_provider_for_screen(self.screen, self.accent_provider)
        Gtk.main_quit()

    def on_key(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if event.keyval == Gdk.KEY_space:
            self.on_play_pause()
            return True
        if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Right) and self.seek.is_focus():
            # Стрелками на слайдере перематываем, а не переключаем трек.
            return False
        if event.keyval == Gdk.KEY_Left:
            self.on_prev()
            return True
        if event.keyval == Gdk.KEY_Right:
            self.on_next()
            return True
        return False

    # --- отрисовка ----------------------------------------------------------

    def _cancel_fade(self):
        if self.fade_id:
            GLib.source_remove(self.fade_id)
            self.fade_id = 0
        for widget in (self.cover, self.title_label, self.artist_label, self.album_label):
            widget.set_opacity(1.0)

    def fade_in(self):
        self._cancel_fade()
        widgets = (self.cover, self.title_label, self.artist_label, self.album_label)
        for widget in widgets:
            widget.set_opacity(0.15)
        steps = 10
        self.fade_step = 0

        def tick():
            self.fade_step += 1
            opacity = 0.15 + 0.85 * (self.fade_step / steps)
            for widget in widgets:
                widget.set_opacity(opacity)
            if self.fade_step >= steps:
                for widget in widgets:
                    widget.set_opacity(1.0)
                self.fade_id = 0
                return False
            self.fade_id = GLib.timeout_add(15, tick)
            return False

        self.fade_id = GLib.timeout_add(15, tick)

    def apply_accent(self, color):
        foreground = accent_foreground(color)
        soft = accent_soft(color)
        css = (
            "#player-card {{ border-top-color: {accent}; }}\n"
            "#popup-title {{ color: {accent}; }}\n"
            "scale trough highlight {{ background-color: {accent}; }}\n"
            "scale trough slider {{ background-color: {accent}; }}\n"
            ".control-btn:hover {{ background-color: {soft}; color: {accent}; }}\n"
            ".control-btn:active {{ background-color: {accent}; color: {foreground}; }}\n"
            ".control-btn:focus {{ background-color: {soft}; color: {accent}; outline-color: {accent}; }}\n"
            "#play-btn:hover {{ background-color: {accent}; color: {foreground}; }}\n"
            "#play-btn:active {{ background-color: {accent}; color: {foreground}; }}\n"
            ".mode-btn.active {{ color: {accent}; }}\n"
        ).format(accent=color, foreground=foreground, soft=soft)
        self.accent_provider.load_from_data(css.encode("utf-8"))

    def set_placeholder(self):
        theme = Gtk.IconTheme.get_default()
        for name in ("audio-x-generic", "media-optical", "applications-multimedia"):
            try:
                pb = theme.load_icon(name, 44, 0)
            except GLib.Error:
                continue
            self.cover.set_from_pixbuf(pb)
            return
        self.cover.set_from_icon_name("audio-x-generic", Gtk.IconSize.DIALOG)
        self.apply_accent(DEFAULT_ACCENT)

    def set_cover(self, path):
        pb = load_cover(path)
        if pb is None:
            self.set_placeholder()
        else:
            self.cover.set_from_pixbuf(pb)
            if ACCENT_MODE == "cover":
                self.apply_accent(pixbuf_accent(pb))
            else:
                self.apply_accent(DEFAULT_ACCENT)

    def _set_mode_active(self, button, active):
        ctx = button.get_style_context()
        if active:
            ctx.add_class("active")
        else:
            ctx.remove_class("active")

    def _update_modes(self, st):
        key = st.get("mode_key")
        if key != self.mode_key:
            self.mode_key = key
            self.shuffle_btn.hide()
            self.loop_btn.hide()
            self._set_mode_active(self.shuffle_btn, False)
            self._set_mode_active(self.loop_btn, False)

        shuffle = st.get("shuffle")
        show_shuffle, show_loop = mode_visibility(shuffle, st.get("loop"))
        if not show_shuffle:
            self.shuffle_btn.hide()
        else:
            self.shuffle_btn.show()
            self.shuffle_btn.set_label("󰒝")
            self.shuffle_btn.set_tooltip_text(
                t("menu.shuffle_status", state=t("mode." + shuffle))
            )
            self._set_mode_active(self.shuffle_btn, shuffle == "on")

        loop = st.get("loop")
        if not show_loop:
            self.loop_btn.hide()
        else:
            self.loop_btn.show()
            self.loop_btn.set_label("󰑘" if loop == "track" else "󰑖")
            self.loop_btn.set_tooltip_text(
                t("menu.loop_status", state=t("mode." + loop))
            )
            self._set_mode_active(self.loop_btn, loop != "none")

    def _update_volume(self, st):
        marked = (
            self.volume_ineffective_key is not None
            and self.volume_ineffective_key == self.volume_key
        )
        self.volume_mode = volume_mode_for(VOLUME_MODE, st["status"], marked)
        if st["volume"] is None and self.volume_mode == "player":
            self.volume_mode = "hidden"
        if self.volume_mode == "hidden":
            self.vol_btn.hide()
            self.vol_scale.hide()
            if self.info_stack.get_visible_child_name() == "volume":
                self.info_stack.set_visible_child_name("status")
            return

        self.vol_btn.show()
        self.vol_scale.show()
        if self.volume_mode == "sink":
            system = wpctl_get_volume()
            if system is None:
                self.volume_mode = "hidden"
                self.vol_btn.hide()
                self.vol_scale.hide()
                if self.info_stack.get_visible_child_name() == "volume":
                    self.info_stack.set_visible_child_name("status")
                return
            pct = int(round(system * 100))
            self.vol_title.set_text(t("menu.system_volume"))
        else:
            pct = int(round((st["volume"] or 0.0) * 100))
            self.vol_title.set_text(t("menu.volume"))

        self.vol_btn.set_sensitive(True)
        self.vol_btn.set_label(volume_icon(pct))
        self.vol_value.set_text(f"{pct}%")
        self.vol_scale.set_sensitive(True)
        if not self.vol_dragging:
            self.updating_vol = True
            self.vol_scale.set_value(pct)
            self.updating_vol = False

    def set_controls_sensitive(self, sensitive):
        for widget in (self.prev_btn, self.play_btn, self.next_btn, self.vol_btn):
            widget.set_sensitive(sensitive)
        if not sensitive:
            self.seek.set_sensitive(False)

    def set_disconnected(self):
        self.state = None
        self.set_controls_sensitive(False)
        self.seek.set_sensitive(False)
        self.title_label.set_text(t("player.unavailable"))
        self.artist_label.set_text("")
        self.album_label.set_text("")
        self.artist_label.hide()
        self.album_label.hide()
        self.play_btn.set_label("󰐊")
        self.cur_label.set_text("—:—")
        self.total_label.set_text("—:—")
        self.vol_btn.set_sensitive(False)
        self.vol_btn.set_label("󰝟")
        self.vol_value.set_text("—")
        self.vol_scale.set_sensitive(False)
        self.status_label.set_text(t("player.no_active"))
        self.info_stack.set_visible_child_name("status")
        self.shuffle_btn.hide()
        self.loop_btn.hide()
        self.last_track_key = None
        self._cancel_fade()
        self.volume_mode = "hidden"
        self.player = ""
        self.selected = None
        self.volume_key = None
        self.volume_ineffective_key = None
        self.mode_key = None
        self.vol_btn.hide()
        self.vol_scale.hide()
        if self.volume_readback_id:
            GLib.source_remove(self.volume_readback_id)
            self.volume_readback_id = 0
        self.length = None
        self.art_token += 1
        if self.art_url is not None:
            self.art_url = None
            self.set_placeholder()

    def _fetch_cover(self, token, url):
        path = fetch_art(url)
        GLib.idle_add(self._apply_cover, token, url, path)

    def _apply_cover(self, token, url, path):
        if not self.alive or token != self.art_token or url != self.art_url:
            return False
        self.set_cover(path)
        return False

    def update_from_state(self, st):
        self.state = st
        new_player = st["player"] or "MPRIS"
        if new_player != self.player:
            if self.volume_readback_id:
                GLib.source_remove(self.volume_readback_id)
                self.volume_readback_id = 0
            self.player = new_player
        new_volume_key = volume_track_key(st)
        if new_volume_key != self.volume_key:
            self.volume_key = new_volume_key
            self.volume_ineffective_key = None
            if self.volume_readback_id:
                GLib.source_remove(self.volume_readback_id)
                self.volume_readback_id = 0
        self.set_controls_sensitive(True)
        self._update_modes(st)

        key = (st["player"], st["title"], st["artist"], st["album"], st["art_url"])
        track_changed = self.last_track_key is not None and key != self.last_track_key
        self.last_track_key = key

        title = st["title"] or st["artist"] or st["player"] or t("status.no_title")
        self.title_label.set_text(title)
        self.artist_label.set_text(st["artist"])
        self.album_label.set_text(st["album"])
        self.artist_label.set_visible(bool(st["artist"]))
        self.album_label.set_visible(bool(st["album"]))

        playing = st["status"] == "playing"
        self.play_btn.set_label("󰏤" if playing else "󰐊")
        self.play_btn.set_tooltip_text(t("menu.pause") if playing else t("menu.play"))

        status_ru = {"playing": t("status.playing"), "paused": t("status.paused")}.get(st["status"], t("status.stopped"))
        player = self.player
        self.status_label.set_text(t("menu.status", player=player, status=status_ru))
        self.status_label.set_tooltip_text(f"{title}\n{st['artist']}")

        if self.art_url != st["art_url"]:
            self.art_url = st["art_url"]
            self.art_token += 1
            self.set_placeholder()
            if self.art_url:
                token = self.art_token
                threading.Thread(
                    target=self._fetch_cover,
                    args=(token, self.art_url),
                    daemon=True,
                ).start()

        if track_changed:
            self.fade_in()

        self._update_volume(st)

        length = st["length"] or 0.0
        if self.length is None or abs(length - self.length) > 0.5:
            self.length = length
            self.updating_seek = True
            if length > 0:
                self.seek.set_range(0, length)
                self.seek.set_sensitive(True)
                self.total_label.set_text(fmt_time(length))
            else:
                self.seek.set_range(0, 1)
                self.seek.set_value(0)
                self.seek.set_sensitive(False)
                self.total_label.set_text("—:—")
            self.updating_seek = False

        pos = st["position"] or 0.0
        if self.length and self.length > 0:
            if (not self.seek_dragging) and (time.monotonic() - self.last_seek > 0.8):
                shown = min(pos, self.length)
                self.updating_seek = True
                self.seek.set_value(shown)
                self.updating_seek = False
                self.cur_label.set_text(fmt_time(shown))

    def refresh(self):
        if not self.alive:
            return False
        selected = players.update_selection()
        if not selected:
            self.set_disconnected()
            return True
        self.selected = selected
        st = get_state(selected)
        if st is None:
            self.set_disconnected()
        else:
            self.update_from_state(st)
        return True

    def refresh_once(self):
        self.refresh()
        return False

    # --- действия -----------------------------------------------------------

    def run_action(self, *args):
        selected = players.update_selection() or self.selected
        if not selected:
            return
        pctl(*args, player=selected, timeout=2)
        # Меню НЕ закрывается после play/pause/next: это раздражало.
        GLib.timeout_add(180, self.refresh_once)

    def on_prev(self, *_args):
        self.run_action("previous")

    def on_play_pause(self, *_args):
        self.run_action("play-pause")

    def on_next(self, *_args):
        self.run_action("next")

    def on_shuffle(self, *_args):
        if self.state is None or self.state.get("shuffle") is None:
            return
        self.run_action("shuffle", "Toggle")

    def on_loop(self, *_args):
        if self.state is None:
            return
        target = next_loop(self.state.get("loop"))
        command = loop_command(target)
        if command:
            self.run_action("loop", command)

    # --- громкость ----------------------------------------------------------

    def toggle_volume_page(self, *_args):
        if self.info_stack.get_visible_child_name() == "volume":
            self.info_stack.set_visible_child_name("status")
            return
        if self.state is None or self.volume_mode == "hidden":
            return
        if self.volume_mode == "sink":
            value = wpctl_get_volume()
            if value is None:
                return
        else:
            value = self.state.get("volume")
            if value is None:
                return
        self.updating_vol = True
        self.vol_scale.set_value(int(round(value * 100)))
        self.updating_vol = False
        self.info_stack.set_visible_child_name("volume")

    def on_volume_changed(self, scale):
        pct = int(round(scale.get_value()))
        self.vol_value.set_text(f"{pct}%")
        self.vol_btn.set_label(volume_icon(pct))
        if self.updating_vol or self.volume_mode == "hidden":
            return
        if self.vol_timeout:
            GLib.source_remove(self.vol_timeout)
        self.vol_timeout = GLib.timeout_add(150, self.apply_volume, pct)

    def apply_volume(self, pct):
        self.vol_timeout = 0
        if not self.alive:
            return False
        if self.volume_mode == "sink":
            if wpctl_set_volume(pct / 100):
                GLib.timeout_add(150, self.refresh_once)
            return False
        if self.volume_mode == "hidden":
            return False

        target = pct / 100
        player = self.player
        result = pctl("volume", "{:.2f}".format(target), player=player)
        set_ok = result is not None and result.returncode == 0
        if self.volume_readback_id:
            GLib.source_remove(self.volume_readback_id)
            self.volume_readback_id = 0
        if self.state is not None and self.state["status"] == "playing":
            self.volume_readback_id = GLib.timeout_add(
                250, self._verify_player_volume, target, player, set_ok, self.volume_key
            )
        return False

    def _verify_player_volume(self, target, player, set_ok, key):
        self.volume_readback_id = 0
        if (not self.alive or self.player != player
                or self.volume_key != key or self.state is None):
            return False
        result = pctl("volume", player=player)
        actual = None
        if result is not None and result.returncode == 0:
            try:
                actual = float(result.stdout.strip())
            except (TypeError, ValueError):
                actual = None
        if volume_check_marks(self.state["status"], set_ok, actual, target):
            self.volume_ineffective_key = self.volume_key
            self.refresh_once()
        return False

    def on_volume_press(self, *_args):
        self.vol_dragging = True

    def on_volume_release(self, *_args):
        self.vol_dragging = False
        if self.vol_timeout:
            GLib.source_remove(self.vol_timeout)
            self.vol_timeout = 0
        self.apply_volume(int(round(self.vol_scale.get_value())))
        return False

    # --- перемотка ----------------------------------------------------------

    def on_seek_changed(self, scale):
        self.cur_label.set_text(fmt_time(scale.get_value()))
        if self.updating_seek or self.seek_dragging:
            return
        if self.seek_timeout:
            GLib.source_remove(self.seek_timeout)
        self.seek_timeout = GLib.timeout_add(250, self.commit_seek)

    def on_seek_press(self, *_args):
        self.seek_dragging = True

    def on_seek_release(self, *_args):
        self.seek_dragging = False
        if self.seek_timeout:
            GLib.source_remove(self.seek_timeout)
            self.seek_timeout = 0
        self.commit_seek()
        return False

    def commit_seek(self):
        self.seek_timeout = 0
        if not self.alive or not self.length or self.length <= 0:
            return False
        target = max(0.0, min(float(self.seek.get_value()), float(self.length)))
        pctl("position", f"{target:.3f}", player=self.player, timeout=2)
        self.last_seek = time.monotonic()
        self.cur_label.set_text(fmt_time(target))
        GLib.timeout_add(200, self.refresh_once)
        return False


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)
    cleanup_cover_cache()
    settings = Gtk.Settings.get_default()
    if settings is not None:
        settings.set_property("gtk-application-prefer-dark-theme", True)

    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    popup = PlayerPopup()
    popup.show()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
