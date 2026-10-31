"""Shared explicit MPRIS player selection for waybar-player."""

import fcntl
import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

PLAYERCTL_TIMEOUT = 1.5
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "waybar-player"
STATE_FILE = RUNTIME_DIR / "selection.json"
LOCK_FILE = RUNTIME_DIR / ".selection.lock"


def _run(args, timeout=PLAYERCTL_TIMEOUT):
    try:
        return subprocess.run(
            ["playerctl", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def list_players():
    result = _run(["-l"])
    if result is None or result.returncode != 0:
        return []
    players = []
    for line in result.stdout.splitlines():
        name = line.strip()
        if name and name not in players:
            players.append(name)
    return players


def player_status(name):
    result = _run(["-p", name, "status"])
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip().lower() or None


def player_metadata(name, fmt):
    result = _run(["-p", name, "metadata", "--format", fmt])
    if result is None or result.returncode != 0:
        return None
    return result.stdout.rstrip("\n")


def priority_patterns():
    raw = os.environ.get("WAYBAR_PLAYER_PRIORITY", "")
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


def _priority_rank(name, patterns):
    lower = name.lower()
    for index, pattern in enumerate(patterns):
        if pattern in lower:
            return index
    return len(patterns)


def select_player(players, statuses, current=None, last_active=None, priority=None):
    """Choose one player; Playing wins, then sticky, then priority/recent."""
    players = list(players)
    if not players:
        return None
    patterns = priority_patterns() if priority is None else [p.lower() for p in priority]
    last_active = last_active or {}
    playing = [name for name in players if statuses.get(name) == "playing"]

    # If the current player is playing, do not jump between two playing players.
    if current in playing:
        return current

    if playing:
        return min(
            playing,
            key=lambda name: (
                _priority_rank(name, patterns),
                -float(last_active.get(name, 0.0)),
                players.index(name),
            ),
        )

    # Nothing is playing: keep the sticky player.
    if current in players:
        return current

    return min(
        players,
        key=lambda name: (
            _priority_rank(name, patterns),
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


def update_selection(players=None, statuses=None):
    """Return the selected player and persist the sticky/recent state."""
    with _locked():
        state = _load_state()
        current = state.get("current")
        last_active = state.get("last_active") or {}

        if players is None:
            players = list_players()
        if statuses is None:
            statuses = {name: player_status(name) for name in players}

        now = time.time()
        for name in players:
            if statuses.get(name) == "playing":
                last_active[name] = now

        selected = select_player(players, statuses, current, last_active)
        state = {
            "version": 1,
            "current": selected,
            "last_active": last_active,
        }
        _save_state(state)
        return selected
