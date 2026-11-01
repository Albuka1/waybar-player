"""Shared explicit MPRIS player selection and sticky state."""

import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

MPRIS_PREFIX = "org.mpris.MediaPlayer2."
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "waybar-player"
STATE_FILE = RUNTIME_DIR / "selection.json"
LOCK_FILE = RUNTIME_DIR / ".selection.lock"


def base_name(full_name):
    if full_name.startswith(MPRIS_PREFIX):
        full_name = full_name[len(MPRIS_PREFIX):]
    return full_name.split(".")[0]


def priority_patterns():
    raw = os.environ.get("WAYBAR_PLAYER_PRIORITY", "")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _identity_fields(name, identities):
    info = (identities or {}).get(name, {})
    fields = [
        info.get("desktop_entry") or "",
        info.get("identity") or "",
        info.get("base") or base_name(name),
    ]
    return [field.lower() for field in fields if field]


def _priority_rank(name, patterns, identities):
    fields = _identity_fields(name, identities)
    for index, pattern in enumerate(patterns):
        if any(pattern in field for field in fields):
            return index
    return len(patterns)


def select_player(players, statuses, current=None, last_active=None,
                  priority=None, identities=None):
    """Choose one full MPRIS bus name; Playing wins, then sticky, then priority."""
    players = list(players)
    if not players:
        return None
    patterns = priority_patterns() if priority is None else [p.lower() for p in priority]
    last_active = last_active or {}
    playing = [name for name in players if statuses.get(name) == "playing"]

    if current in playing:
        return current

    if playing:
        return min(
            playing,
            key=lambda name: (
                _priority_rank(name, patterns, identities),
                -float(last_active.get(name, 0.0)),
                players.index(name),
            ),
        )

    if current in players:
        return current

    return min(
        players,
        key=lambda name: (
            _priority_rank(name, patterns, identities),
            -float(last_active.get(name, 0.0)),
            players.index(name),
        ),
    )


@contextmanager
def _locked():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(LOCK_FILE), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _load_state():
    try:
        with STATE_FILE.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return {}
    return state if isinstance(state, dict) else {}


def _save_state(state):
    temporary = RUNTIME_DIR / (".selection.{}.tmp".format(os.getpid()))
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(temporary, STATE_FILE)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass


def update_selection(players, statuses, identities=None):
    """Return the selected full bus name and persist sticky/recent state."""
    with _locked():
        state = _load_state()
        current = state.get("current")
        last_active = state.get("last_active") or {}

        now = time.time()
        for name in players:
            if statuses.get(name) == "playing":
                last_active[name] = now

        selected = select_player(
            players, statuses, current, last_active, identities=identities
        )
        state = {
            "version": 2,
            "current": selected,
            "last_active": last_active,
        }
        _save_state(state)
        return selected
