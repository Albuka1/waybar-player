from pathlib import Path

import players


def test_playing_beats_paused():
    players_list = ["A", "B"]
    statuses = {"A": "playing", "B": "paused"}
    assert players.select_player(players_list, statuses, current="B") == "A"


def test_playing_b_is_selected_when_a_is_paused():
    statuses = {"A": "paused", "B": "playing"}
    assert players.select_player(["A", "B"], statuses, current="A") == "B"


def test_two_playing_players_keep_current():
    statuses = {"A": "playing", "B": "playing"}
    assert players.select_player(["A", "B"], statuses, current="B") == "B"


def test_nothing_playing_keeps_current():
    statuses = {"A": "paused", "B": "stopped"}
    assert players.select_player(["A", "B"], statuses, current="B") == "B"


def test_priority_is_tiebreak_when_no_current_is_playing():
    statuses = {"A": "playing", "B": "playing"}
    selected = players.select_player(
        ["A", "B"], statuses, current=None, priority=["B"]
    )
    assert selected == "B"


def test_recent_activity_is_used_without_current():
    statuses = {"A": "paused", "B": "paused"}
    selected = players.select_player(
        ["A", "B"], statuses, current=None, last_active={"A": 10.0, "B": 20.0}
    )
    assert selected == "B"


def test_update_selection_persists_sticky_current(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setattr(players, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(players, "STATE_FILE", runtime / "selection.json")
    monkeypatch.setattr(players, "LOCK_FILE", runtime / ".lock")
    statuses = {"A": "paused", "B": "stopped"}
    monkeypatch.setattr(players, "list_players", lambda: ["A", "B"])
    monkeypatch.setattr(players, "player_status", lambda name: statuses[name])

    assert players.update_selection() == "A"
    assert players.update_selection() == "A"
    assert players.STATE_FILE.is_file()
