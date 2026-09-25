"""Doubles for the one boundary the command layer has: the recorder.

Everything below `recorder.record` is a subprocess, so it is replaced. Nothing
else is: resolution, path building, overwrite checks and error handling all run
for real, which is the point - these tests exercise the code that runs when
someone types a command.
"""

import copy

import pytest

from cinta.core import media, recorder

TARGETS = {
    "displays": [
        {
            "index": 1,
            "id": 2,
            "name": "Mi Monitor",
            "isMain": False,
            "pixelWidth": 3440,
            "pixelHeight": 1440,
        },
        {
            "index": 2,
            "id": 3,
            "name": "ARZOPA",
            "isMain": False,
            "pixelWidth": 1920,
            "pixelHeight": 1200,
        },
        {
            "index": 3,
            "id": 1,
            "name": "Built-in Retina Display",
            "isMain": True,
            "pixelWidth": 3024,
            "pixelHeight": 1964,
        },
    ],
    "microphones": [
        {
            "index": 1,
            "id": "BuiltInMicrophoneDevice",
            "name": "MacBook Pro Microphone",
            "isDefault": True,
        },
        {"index": 2, "id": "USB-Audio", "name": "Yeti Stereo Microphone", "isDefault": False},
    ],
    "windows": [
        {
            "id": 512,
            "app": "Safari",
            "bundleID": "com.apple.Safari",
            "title": "Some page",
            "width": 1440,
            "height": 900,
        }
    ],
    "applications": [{"bundleID": "com.apple.Safari", "name": "Safari", "pid": 403}],
}


@pytest.fixture
def fake_recorder(monkeypatch):
    """Captures what the command layer asked the recorder to do.

    `calls["record"]` is the keyword arguments it was called with, absent if it
    was never called at all - which is itself worth asserting. `calls["mixed"]`
    lists the files handed to ffmpeg.
    """
    calls: dict = {"mixed": []}

    def list_targets():
        return copy.deepcopy(TARGETS)

    def record(**kwargs):
        calls["record"] = kwargs
        output = kwargs["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"pretend this is a movie")
        return {
            "path": str(output),
            "durationSeconds": 5.0,
            "bytes": output.stat().st_size,
            "audioTracks": [],
            "stoppedBy": "duration",
        }

    monkeypatch.setattr(recorder, "list_targets", list_targets)
    monkeypatch.setattr(recorder, "record", record)
    monkeypatch.setattr(media, "mix_audio_tracks", lambda path: calls["mixed"].append(path))
    return calls


@pytest.fixture
def output_dir(monkeypatch, tmp_path):
    """Keeps recordings out of the real ~/cinta while still going through the
    configured-directory path rather than an explicit --output."""
    directory = tmp_path / "out"
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(directory))
    return directory
