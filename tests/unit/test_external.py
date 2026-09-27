"""The subprocess boundary. A fake cintarec stands in for the real binary, so
these tests exercise the JSON contract without recording anything."""

import json
import os
import signal
import stat
import subprocess

import pytest

from cinta import external
from cinta.errors import CintaError

REPORT = {"path": "/tmp/out.mov", "durationSeconds": 5.0, "bytes": 1024, "stoppedBy": "duration"}


def fake_recorder(tmp_path, stdout="", exit_code=0, stderr=""):
    script = tmp_path / "cintarec"
    script.write_text(
        f"#!/bin/sh\ncat <<'OUT'\n{stdout}\nOUT\necho '{stderr}' >&2\nexit {exit_code}\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_environment_variable_selects_the_recorder(monkeypatch, tmp_path):
    script = fake_recorder(tmp_path)
    monkeypatch.setenv("CINTA_RECORDER", str(script))
    assert external.recorder_path() == script


def test_missing_recorder_from_environment_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_RECORDER", str(tmp_path / "nope"))
    with pytest.raises(CintaError) as error:
        external.recorder_path()
    assert "not a file" in error.value.message


def test_report_is_parsed_from_stdout(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_RECORDER", str(fake_recorder(tmp_path, stdout=json.dumps(REPORT))))
    assert external.run_recorder(["--duration", "5"]) == REPORT


def test_missing_screen_permission_explains_the_fix(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_RECORDER", str(fake_recorder(tmp_path, exit_code=10)))
    with pytest.raises(CintaError) as error:
        external.run_recorder(["--list"])
    assert error.value.exit_code == 10
    assert "Screen" in error.value.hint


def test_missing_target_points_at_the_listing(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_RECORDER", str(fake_recorder(tmp_path, exit_code=12)))
    with pytest.raises(CintaError) as error:
        external.run_recorder(["--display", "id:99"])
    assert error.value.exit_code == 12
    assert "cinta devices" in error.value.hint


def test_unknown_exit_code_surfaces_the_recorder_log(monkeypatch, tmp_path):
    monkeypatch.setenv(
        "CINTA_RECORDER", str(fake_recorder(tmp_path, exit_code=42, stderr="something broke"))
    )
    with pytest.raises(CintaError) as error:
        external.run_recorder([])
    assert "something broke" in error.value.message


def test_output_that_is_not_json_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_RECORDER", str(fake_recorder(tmp_path, stdout="not json")))
    with pytest.raises(CintaError) as error:
        external.run_recorder([])
    assert "not JSON" in error.value.message


STARTED = {"event": "started", "path": "/tmp/out.mov", "startedAt": "2026-09-27T12:00:00.000Z"}


def script(tmp_path, body: str):
    path = tmp_path / "cintarec"
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def test_started_arrives_while_recording_not_after(monkeypatch, tmp_path):
    marker = tmp_path / "still-running"
    recorder = script(
        tmp_path,
        f"touch {marker}\necho '{json.dumps(STARTED)}'\nsleep 1\nrm {marker}\n"
        f"echo '{json.dumps(REPORT)}'\n",
    )
    monkeypatch.setenv("CINTA_RECORDER", str(recorder))
    seen = []

    report = external.run_recorder(
        [], on_started=lambda event: seen.append((event, marker.exists()))
    )

    assert seen == [(STARTED, True)]
    assert report == REPORT


@pytest.mark.parametrize("sent", [signal.SIGINT, signal.SIGTERM])
def test_a_signal_to_cinta_stops_the_recorder_cleanly(monkeypatch, tmp_path, sent):
    """A program stopping cinta signals cinta alone, not its child. cintarec
    has to hear about it as SIGINT, finish the file, and report."""
    stopped = tmp_path / "stopped.json"
    stopped.write_text(json.dumps({**REPORT, "stoppedBy": "signal"}))
    gave_up = {**REPORT, "stoppedBy": "never told"}
    recorder = script(
        tmp_path,
        f"trap 'cat {stopped}; exit 0' INT\n"
        f"echo '{json.dumps(STARTED)}'\n"
        # Gives up on its own, so a broken forward fails the test rather than hanging it.
        "i=0; while [ $i -lt 50 ]; do sleep 0.1; i=$((i+1)); done\n"
        f"echo '{json.dumps(gave_up)}'\n",
    )
    monkeypatch.setenv("CINTA_RECORDER", str(recorder))
    before = signal.getsignal(sent)

    # From another process, as a program driving cinta would: a signal raised
    # inside this one would favour the thread that raised it.
    def stop(event):
        subprocess.Popen(["sh", "-c", f"sleep 0.3; kill -{sent.name[3:]} {os.getpid()}"])

    report = external.run_recorder([], on_started=stop)

    assert report["stoppedBy"] == "signal"
    assert signal.getsignal(sent) == before
