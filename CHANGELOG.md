# Changelog

## 0.4.1

- Fix frozen popup position: local one-second interpolation while Playing,
  re-sync from MPRIS every 5 s and on Seeked/status/track changes.
- Timers start in show and stop in hide; hidden resident popup performs no
  position polling. Drag guard is always cleared on hide.

## 0.4.0

- Direct async MPRIS over Gio D-Bus; no playerctl.
- Full bus-name identity and identity-based `WAYBAR_PLAYER_PRIORITY`.
- Event-driven status with 50 ms debounce and 30 s resync.
- Resident popup with seeded first frame and deferred refresh/workspace work.
- `waybar-player-ctl` uses full-bus D-Bus commands.
- Tests use a fake MPRIS service on a private session bus.
