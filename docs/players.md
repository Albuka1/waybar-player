# MPRIS players and identity

waybar-player talks to MPRIS directly over Gio D-Bus. It never uses a shell
player controller and never relies on an implicit "first player" for commands.

## Identity

A player is identified everywhere by its **full bus name**:

```text
org.mpris.MediaPlayer2.chromium.instance123
org.mpris.MediaPlayer2.firefox.instance456
```

Base names such as `chromium` and `firefox` are used only for display. Identity
matching for `WAYBAR_PLAYER_PRIORITY` checks, in order:

1. `DesktopEntry`
2. `Identity`
3. base bus name

This distinguishes an Electron app (for example Yandex Music, desktop entry
`yandex-music`, identity `YandexMusic`) from Chromium/Firefox when both expose
a `chromium.instanceN`-style bus name.

## Selection policy

Shared by status, popup and ctl:

1. If the current player is Playing, keep it while it plays.
2. Otherwise Playing wins over Paused/Stopped.
3. Among equals: `WAYBAR_PLAYER_PRIORITY`, then the sticky current player,
   then the most recently active player.
4. If nothing plays, keep the sticky player.
5. If there is no usable player, status outputs the idle JSON and ctl exits 1.

State is stored in `$XDG_RUNTIME_DIR/waybar-player/selection.json` under
`flock`, with atomic replacement.

## Diagnostics with gdbus

List MPRIS names:

```bash
gdbus call --session \
  --dest org.freedesktop.DBus \
  --object-path /org/freedesktop/DBus \
  --method org.freedesktop.DBus.ListNames
```

Read a property by full bus name:

```bash
gdbus call --session \
  --dest org.mpris.MediaPlayer2.chromium.instance123 \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.freedesktop.DBus.Properties.Get \
  org.mpris.MediaPlayer2.Player PlaybackStatus
```

Read root identity:

```bash
gdbus call --session \
  --dest org.mpris.MediaPlayer2.chromium.instance123 \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.freedesktop.DBus.Properties.Get \
  org.mpris.MediaPlayer2 Identity
```

Read metadata:

```bash
gdbus call --session \
  --dest org.mpris.MediaPlayer2.chromium.instance123 \
  --object-path /org/mpris/MediaPlayer2 \
  --method org.freedesktop.DBus.Properties.Get \
  org.mpris.MediaPlayer2.Player Metadata
```

Read the current selection:

```bash
cat "${XDG_RUNTIME_DIR:-/tmp}/waybar-player/selection.json"
```

## Firefox cover art

Firefox should be checked while it has an active MPRIS session. Read
`mpris:artUrl` with the Metadata command above. A `file://` URL is accepted only
inside the documented whitelist (`/tmp`, `$XDG_RUNTIME_DIR`, the cache
directory, and `WAYBAR_PLAYER_ART_DIRS`); outside paths are rejected by design.
