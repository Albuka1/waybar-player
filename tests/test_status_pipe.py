import json
import os
import selectors
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "bin" / "waybar-player-status"


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
    raise AssertionError("status line did not arrive: {}".format(predicate))


def _fake_playerctl(tmp_path):
    path = tmp_path / "playerctl"
    path.write_text(
        '''#!/usr/bin/env python3
import os
import sys
import time

state_path = os.environ["FAKE_PLAYER_STATE"]


def state():
    with open(state_path, encoding="utf-8") as handle:
        return handle.read().strip() or "Playing"


args = sys.argv[1:]
if args == ["-l"]:
    print("fakeplayer")
    sys.exit(0)
if args[:1] == ["-p"]:
    command = args[2] if len(args) > 2 else ""
    current = state()
    if command == "status":
        print(current)
        sys.exit(0)
    if command == "metadata":
        print("\\x1f".join([current, "fakeplayer", "Title", "Artist", "Album", "", "0.5"]))
        sys.exit(0)
    sys.exit(1)
if args[:2] == ["-a", "--follow"]:
    while True:
        time.sleep(0.2)
sys.exit(1)
''',
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_stdout_pipe_reports_pause_within_one_second(tmp_path):
    fake = _fake_playerctl(tmp_path)
    state_file = tmp_path / "state"
    state_file.write_text("Playing\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()

    env = os.environ.copy()
    env["PATH"] = str(tmp_path) + os.pathsep + env.get("PATH", "")
    env["FAKE_PLAYER_STATE"] = str(state_file)
    env["XDG_RUNTIME_DIR"] = str(runtime)
    env["WAYBAR_PLAYER_LANG"] = "en"

    proc = subprocess.Popen(
        [str(STATUS)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    try:
        playing = _read_until(proc, lambda p: p.get("class") == "playing")
        assert playing["text"]

        started = time.monotonic()
        state_file.write_text("Paused\n", encoding="utf-8")
        paused = _read_until(proc, lambda p: p.get("class") == "paused", timeout=2.5)
        elapsed = time.monotonic() - started
        assert paused["text"].startswith("󰏤")
        assert elapsed < 2.5

        state_file.write_text("Playing\n", encoding="utf-8")
        resumed = _read_until(proc, lambda p: p.get("class") == "playing", timeout=2.5)
        assert resumed["text"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
