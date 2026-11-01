import types

from helpers import load_module

menu = load_module("waybar_player_menu", "share/player-menu.py")


class FakePopup:
    pass


def make_popup(now=100.0, status="playing"):
    popup = FakePopup()
    popup.state = {"status": status, "player": "A", "title": "T", "artist": "A", "album": ""}
    popup.position = 10.0
    popup.position_time = now
    popup.position_sync_at = now
    popup.position_supported = True
    popup.seek_dragging = False
    popup.length = 120.0
    popup.selected_player = types.SimpleNamespace(rate=1.0)
    popup.displayed = []
    popup.resyncs = []
    popup._display_position = lambda: popup.displayed.append(popup.position)
    popup._resync_position = lambda: popup.resyncs.append(popup.position)
    return popup


def test_position_advances_while_playing(monkeypatch):
    popup = make_popup()
    now = [100.0]
    monkeypatch.setattr(menu.time, "monotonic", lambda: now[0])
    menu.PlayerPopup._advance_position(popup)
    now[0] = 103.0
    menu.PlayerPopup._advance_position(popup)
    assert abs(popup.position - 13.0) < 0.01
    assert popup.displayed[-1] == popup.position


def test_pause_stops_position_and_resume_continues(monkeypatch):
    popup = make_popup()
    now = [100.0]
    monkeypatch.setattr(menu.time, "monotonic", lambda: now[0])
    menu.PlayerPopup._advance_position(popup)
    now[0] = 103.0
    popup.state["status"] = "paused"
    menu.PlayerPopup._advance_position(popup)
    paused = popup.position
    now[0] = 106.0
    menu.PlayerPopup._advance_position(popup)
    assert popup.position == paused
    popup.state["status"] = "playing"
    now[0] = 107.0
    menu.PlayerPopup._advance_position(popup)
    assert popup.position > paused


def test_seeked_resyncs_position(monkeypatch):
    popup = make_popup()
    popup.alive = True
    popup.visible = True
    popup.selected_player = object()
    popup._display_position = lambda: None
    popup.position = 1.0
    menu.PlayerPopup._manager_seeked(popup, popup.selected_player, 42.0)
    assert popup.position == 42.0


def test_reset_position_on_track_change(monkeypatch):
    popup = make_popup()
    monkeypatch.setattr(menu.time, "monotonic", lambda: 100.0)
    popup.position = 50.0
    popup.position_sync_at = 50.0
    menu.PlayerPopup._reset_position(popup)
    assert popup.position == 0.0
    assert popup.position_sync_at == 0.0
    assert popup.position_supported is True


def test_hidden_popup_has_no_refresh_timer(monkeypatch):
    popup = make_popup()
    popup.alive = True
    popup.visible = False
    calls = []
    popup._advance_position = lambda: calls.append("advance")
    popup.refresh = lambda: calls.append("refresh")
    assert menu.PlayerPopup._refresh_tick(popup) is False
    assert calls == []

    popup.visible = True
    assert menu.PlayerPopup._refresh_tick(popup) is True
    assert calls == ["advance", "refresh"]


def test_hide_clears_drag_guard():
    popup = make_popup()
    popup.alive = True
    popup.visible = True
    popup.resident = True
    popup.seek_dragging = True
    popup.updating_seek = True
    popup.workspace_id = 3
    popup.win = types.SimpleNamespace(hide=lambda: None)
    popup._cancel_timers = lambda: None
    menu.PlayerPopup.close(popup)
    assert popup.seek_dragging is False
    assert popup.updating_seek is False
    assert popup.visible is False
