# MPRIS diagnostics

Date: 2026-10-31. Yandex Music in Chromium.

## `playerctl -l`

```text
chromium.instance125864
```

## `playerctl -a metadata --format '{{playerName}} {{status}}'`

```text
chromium Paused
```

## Chromium (`chromium.instance125864`)

```text
$ playerctl -p chromium.instance125864 volume
1.000000
$ playerctl -p chromium.instance125864 shuffle
No player could handle this command
$ playerctl -p chromium.instance125864 loop
No player could handle this command
$ playerctl -p chromium.instance125864 volume 0.3
$ playerctl -p chromium.instance125864 volume   # after ~350 ms
1.000000
```

Conclusions:

- Chromium advertises a volume property, but setting it to `0.3` did not
  change the reported value (`1.000000`); the volume control is ineffective.
- Shuffle and loop are not supported; the popup hides those buttons.
- The volume fallback (`WAYBAR_PLAYER_VOLUME_FALLBACK`, default `sink`) is
  therefore required for this player.

## Firefox

```text
$ playerctl -l
chromium.instance125864
$ playerctl -p firefox volume
No players found
$ playerctl -p firefox metadata mpris:artUrl
No players found
```

Firefox was not running an MPRIS media session during this check, so its
`mpris:artUrl` could not be inspected. The Firefox artwork issue is not
reproduced here; it is not treated as a confirmed whitelist regression. When
Firefox is playing, `playerctl -p firefox metadata mpris:artUrl` should be
checked for scheme and path against the whitelist in `fetch_art()`.
