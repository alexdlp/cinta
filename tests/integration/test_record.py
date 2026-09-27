"""A real recording, checked with ffprobe.

Marked `recording` rather than `integration` because it needs what no CI runner
has: a display, and the screen recording permission granted to the terminal
running it. Run it by hand after touching cintarec or before a release:

    uv run pytest -m recording

It needs the recorder built (`make build-swift`).
"""

import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from cinta.cli import main

from .conftest import duration

pytestmark = pytest.mark.recording


def streams(path: Path) -> list[dict]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["streams"]


@pytest.mark.parametrize(("audio", "audio_tracks"), [("system", 1), ("none", 0)])
def test_three_seconds_of_screen(tmp_path, audio, audio_tracks):
    output = tmp_path / "recording.mov"

    exit_code = main(["record", "3s", "--audio", audio, "--output", str(output)])

    assert exit_code == 0
    assert duration(output) == pytest.approx(3, abs=0.5)

    found = streams(output)
    video = [stream for stream in found if stream["codec_type"] == "video"]
    sound = [stream for stream in found if stream["codec_type"] == "audio"]
    assert [stream["codec_name"] for stream in video] == ["h264"]
    assert int(video[0]["width"]) % 2 == 0
    assert int(video[0]["height"]) % 2 == 0
    assert len(sound) == audio_tracks
    assert all(stream["codec_name"] == "aac" for stream in sound)


@pytest.mark.parametrize("stop_with", [signal.SIGINT, signal.SIGTERM])
def test_driven_by_a_program(tmp_path, stop_with):
    """The way another tool drives cinta: start it, wait for the "started" line
    before playing anything, signal cinta alone (not its process group), and
    read the report from the "finished" line. The file must play."""
    output = tmp_path / "driven.mov"
    process = subprocess.Popen(
        [sys.executable, "-m", "cinta", "--json", "record", "--audio", "none", "--output", output],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        started = json.loads(process.stdout.readline())
        assert started["event"] == "started"
        assert started["path"] == str(output)
        began = time.monotonic()

        time.sleep(2)
        process.send_signal(stop_with)
        finished = json.loads(process.stdout.readline())
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.kill()

    assert finished["event"] == "finished"
    assert finished["stoppedBy"] == "signal"
    # The file starts at the "started" line, so its length is the time since.
    assert duration(output) == pytest.approx(time.monotonic() - began, abs=0.6)
