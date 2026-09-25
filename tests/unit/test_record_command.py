"""cinta record, end to end with the recorder replaced."""

import re

import pytest

from cinta.cli import main


def test_output_lands_in_the_configured_directory_with_a_timestamped_name(
    fake_recorder, output_dir
):
    """The naming contract reaching the recorder, not just the helper that builds
    it: config.output_dir and recorder.output_path have to be wired together in
    the right order for a recording to end up where DESIGN.md 4.0 says."""
    assert main(["record", "--display", "1", "2s"]) == 0

    written = fake_recorder["record"]["output"]
    assert written.parent == output_dir
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{6}-MiMonitor\.mov", written.name)


def test_explicit_output_is_used_exactly_as_given(fake_recorder, tmp_path, output_dir):
    """--output must win outright, not be joined to the configured directory."""
    target = tmp_path / "somewhere" / "demo.mov"
    assert main(["record", "--display", "1", "--output", str(target), "2s"]) == 0
    assert fake_recorder["record"]["output"] == target


def test_an_existing_file_is_refused_before_anything_is_recorded(
    fake_recorder, tmp_path, output_dir
):
    """Order matters more than the refusal. Checking after recording would mean
    spending five minutes capturing and then throwing the result away, so this
    asserts the recorder was never started and the old file is untouched."""
    target = tmp_path / "taken.mov"
    target.write_bytes(b"something I care about")

    assert main(["record", "--display", "1", "--output", str(target), "2s"]) == 13
    assert "record" not in fake_recorder
    assert target.read_bytes() == b"something I care about"


def test_force_replaces_the_existing_file(fake_recorder, tmp_path, output_dir):
    """The escape hatch has to actually work, or --force is a lie."""
    target = tmp_path / "taken.mov"
    target.write_bytes(b"old")

    assert main(["record", "--display", "1", "--output", str(target), "--force", "2s"]) == 0
    assert fake_recorder["record"]["output"] == target
    assert target.read_bytes() != b"old"


@pytest.mark.parametrize(
    ("audio", "expects_microphone"),
    [("system", False), ("none", False), ("mic", True), ("both", True)],
)
def test_the_microphone_is_only_opened_when_the_audio_mode_needs_it(
    fake_recorder, output_dir, audio, expects_microphone
):
    """Resolving a microphone means asking macOS for permission. Doing it for
    --audio system would pop a permission dialog for a device nobody asked to
    record."""
    assert main(["record", "--display", "1", "--audio", audio, "2s"]) == 0
    assert (fake_recorder["record"]["microphone"] is not None) is expects_microphone


@pytest.mark.parametrize(
    ("arguments", "should_mix"),
    [
        (["--audio", "system"], False),
        (["--audio", "mic"], False),
        (["--audio", "both"], True),
        (["--audio", "both", "--keep-tracks"], False),
    ],
)
def test_mixing_happens_only_for_both_and_only_without_keep_tracks(
    fake_recorder, output_dir, arguments, should_mix
):
    """Mixing a file that has one audio track would fail; skipping it when there
    are two leaves the echo that made --audio both sound broken."""
    assert main(["record", "--display", "1", *arguments, "2s"]) == 0
    assert bool(fake_recorder["mixed"]) is should_mix


def test_the_duration_reaches_the_recorder_in_seconds(fake_recorder, output_dir):
    """The unit is parsed at the edge and everything below speaks seconds. If the
    conversion were skipped, '5m' would reach cintarec as five."""
    assert main(["record", "--display", "1", "5m"]) == 0
    assert fake_recorder["record"]["duration"] == 300


def test_no_duration_means_no_limit(fake_recorder, output_dir):
    """Omitting it has to mean 'until I stop it', not 'zero seconds'."""
    assert main(["record", "--display", "1"]) == 0
    assert fake_recorder["record"]["duration"] is None


def test_stdout_carries_the_path_and_nothing_else(fake_recorder, output_dir, capsys):
    """`open "$(cinta record ...)"` is the documented way to watch what you just
    recorded, and it only works if every human-facing line went to stderr."""
    assert main(["record", "--display", "1", "2s"]) == 0

    captured = capsys.readouterr()
    assert captured.out.strip() == str(fake_recorder["record"]["output"])
    assert "Recording" in captured.err


def test_capture_options_reach_the_recorder_unchanged(fake_recorder, output_dir):
    """These flags do nothing in this layer except travel. Dropping one is
    invisible until you play the file back and the cursor is still there."""
    assert (
        main(
            [
                "record",
                "--display",
                "arzopa",
                "--fps",
                "60",
                "--scale",
                "0.5",
                "--no-cursor",
                "--codec",
                "hevc",
                "2s",
            ]
        )
        == 0
    )

    call = fake_recorder["record"]
    assert call["display"]["name"] == "ARZOPA"
    assert call["fps"] == 60
    assert call["scale"] == 0.5
    assert call["show_cursor"] is False
    assert call["codec"] == "hevc"
