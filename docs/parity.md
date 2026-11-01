# Parity with 0.3.1

The JSON emitted by `waybar-player-status` is byte-compatible with 0.3.1:

```json
{"text":"...","tooltip":"...","class":"playing|paused|stopped","percentage":N}
```

- `text`, `tooltip`, `class`, `percentage` keep the same meaning and the same
  i18n strings.
- Frames still advance every 0.2 s while Playing; paused/idle text is stable.
- Paused and stopped classes and icons are unchanged.
- The selection policy is unchanged: Playing > Paused, sticky current, priority,
  then recent activity.

## What changed in 0.4.0

- Data source: direct async Gio D-Bus instead of external player processes.
- Identity: full bus name everywhere; base names are display-only.
- Status: PropertiesChanged/NameOwnerChanged events, 50 ms debounce, 30 s safety
  resync, line-buffered output only when the JSON changes.
- Popup: resident hidden window, seeded first frame, deferred refresh and
  workspace checks.
- ctl: full-bus-name D-Bus commands.
- Volume: same 250 ms read-back rule; ineffective-player key is
  `(full bus name, trackid|url|title+artist)`.
- No external player-controller dependency.
