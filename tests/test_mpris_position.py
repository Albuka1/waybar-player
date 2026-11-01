import os
import subprocess
import time
from pathlib import Path

import pytest
from gi.repository import Gio, GLib

import mpris
from test_status_pipe import _start_private_bus, _wait_for_name

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "fake_mpris_service.py"


def test_position_and_seeked_from_fake_mpris(tmp_path):
    address, bus_pid = _start_private_bus()
    state_file = tmp_path / "state"
    state_file.write_text("Playing\n", encoding="utf-8")
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = address
    env["FAKE_MPRIS_STATE"] = str(state_file)
    fake = subprocess.Popen(
        ["python3", str(FAKE)], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    loop = GLib.MainLoop()
    result = {"position": None, "seeked": None}
    manager = None
    try:
        _wait_for_name(address, "org.mpris.MediaPlayer2.fake")

        def on_seeked(_player, position):
            result["seeked"] = position
            loop.quit()

        manager = mpris.MprisManager(on_seeked=on_seeked)

        def ready():
            key = "org.mpris.MediaPlayer2.fake"
            if key not in manager.players or not manager.players[key].ready:
                GLib.timeout_add(50, ready)
                return True
            player = manager.players[key]

            def got_position(value, _error):
                result["position"] = value
                player.set_position("/fake/track/1", 20_000_000)

            player.get_position(got_position)

        connection = Gio.DBusConnection.new_for_address_sync(
            address,
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
            | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None,
        )
        manager.start(ready, connection=connection)
        GLib.timeout_add(3000, loop.quit)
        loop.run()
        assert result["position"] == 10_000_000
        assert result["seeked"] == 20.0
    finally:
        fake.terminate()
        try:
            fake.wait(timeout=3)
        except subprocess.TimeoutExpired:
            fake.kill()
            fake.wait()
        try:
            os.kill(bus_pid, 15)
        except OSError:
            pass
