"""A real recording, checked with ffprobe.

Marked `recording` rather than `integration` because it needs what no CI runner
has: a display, and the screen recording permission granted to the terminal
running it. Run it by hand after touching cintarec or before a release:

    uv run pytest -m recording

It needs the recorder built (`make build-swift`).
"""

import json
import subprocess
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
