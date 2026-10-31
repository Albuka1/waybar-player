import subprocess

from helpers import load_module

ctl = load_module("waybar_player_ctl", "bin/waybar-player-ctl")


def _result(args, code=0, stdout=""):
    return subprocess.CompletedProcess(args, code, stdout, "")


def test_ctl_runs_selected_player(monkeypatch):
    calls = []
    monkeypatch.setattr(ctl.players, "update_selection", lambda: "A")

    def fake_pctl(player, *args, **_kwargs):
        calls.append((player, args))
        return _result(args)

    monkeypatch.setattr(ctl, "pctl", fake_pctl)
    assert ctl.main(["waybar-player-ctl", "play-pause"]) == 0
    assert calls == [("A", ("play-pause",))]


def test_ctl_loop_cycles_on_selected_player(monkeypatch):
    calls = []
    monkeypatch.setattr(ctl.players, "update_selection", lambda: "A")

    def fake_pctl(player, *args, **_kwargs):
        calls.append((player, args))
        if args[0] == "loop":
            return _result(args, 0, "None\n")
        return _result(args)

    monkeypatch.setattr(ctl, "pctl", fake_pctl)
    assert ctl.run("loop", "A")
    assert calls[-1] == ("A", ("loop", "Track"))


def test_ctl_without_player_returns_error(monkeypatch):
    monkeypatch.setattr(ctl.players, "update_selection", lambda: None)
    assert ctl.main(["waybar-player-ctl", "next"]) == 1
