"""The subprocess boundary. A fake cintarec stands in for the real binary, so
these tests exercise the JSON contract without recording anything."""

import json
import stat

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
