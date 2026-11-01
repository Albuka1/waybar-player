import json
import os
import selectors
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "bin" / "waybar-player-status"
FAKE = ROOT / "tests" / "fake_mpris_service.py"


def _read_until(proc, predicate, timeout=3.0):
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            if not selector.select(max(0.0, deadline - time.monotonic())):
                break
            line = proc.stdout.readline()
            if not line:
                break
            try:
                payload = json.loads(line)
            except ValueError:
                continue
            if predicate(payload):
                return payload
    finally:
        selector.close()
    raise AssertionError("status line did not arrive")


def _start_private_bus():
    if shutil.which("dbus-daemon") is None:
        pytest.skip("dbus-daemon is missing")
    proc = subprocess.Popen(
        ["dbus-daemon", "--session", "--fork", "--print-address=1", "--print-pid=1"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    address = proc.stdout.readline().strip()
    pid_text = proc.stdout.readline().strip()
    proc.wait(timeout=5)
    if not address or not pid_text:
        raise RuntimeError("dbus-daemon did not report address/pid")
    return address, int(pid_text)


def _wait_for_name(address, name, timeout=3.0):
    bus = Gio.DBusConnection.new_for_address_sync(
        address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None
    )
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            reply = bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "NameHasOwner",
                GLib.Variant("(s)", (name,)), GLib.VariantType.new("(b)"),
                Gio.DBusCallFlags.NONE, 200, None,
            )
            if reply.unpack()[0]:
                return
        except GLib.Error:
            pass
        time.sleep(0.05)
    raise AssertionError("fake MPRIS name did not appear")


def test_stdout_pipe_reports_pause_within_one_second(tmp_path):
    address, bus_pid = _start_private_bus()
    state_file = tmp_path / "state"
    state_file.write_text("Playing\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = address
    env["FAKE_MPRIS_STATE"] = str(state_file)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env["WAYBAR_PLAYER_LANG"] = "en"

    fake = subprocess.Popen(
        ["python3", str(FAKE)], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    status = None
    try:
        _wait_for_name(address, "org.mpris.MediaPlayer2.fake")
        status = subprocess.Popen(
            [str(STATUS)], env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        playing = _read_until(status, lambda p: p.get("class") == "playing")
        assert playing["text"]

        started = time.monotonic()
        state_file.write_text("Paused\n", encoding="utf-8")
        paused = _read_until(status, lambda p: p.get("class") == "paused", timeout=2.5)
        elapsed = time.monotonic() - started
        assert paused["text"].startswith("󰏤")
        assert elapsed < 2.5

        state_file.write_text("Playing\n", encoding="utf-8")
        resumed = _read_until(status, lambda p: p.get("class") == "playing", timeout=2.5)
        assert resumed["text"]
    finally:
        if status is not None:
            status.terminate()
            try:
                status.wait(timeout=3)
            except subprocess.TimeoutExpired:
                status.kill()
                status.wait(timeout=3)
        fake.terminate()
        try:
            fake.wait(timeout=3)
        except subprocess.TimeoutExpired:
            fake.kill()
            fake.wait(timeout=3)
        try:
            os.kill(bus_pid, 15)
        except OSError:
            pass
