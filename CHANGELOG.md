# Changelog

## 0.4.0

- Direct async MPRIS over Gio D-Bus; no playerctl.
- Full bus-name identity and identity-based `WAYBAR_PLAYER_PRIORITY`.
- Event-driven status with 50 ms debounce and 30 s resync.
- Resident popup with seeded first frame and deferred refresh/workspace work.
- `waybar-player-ctl` uses full-bus D-Bus commands.
- Tests use a fake MPRIS service on a private session bus.
