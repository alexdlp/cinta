"""cinta transcribe, with ffmpeg and whisper-cli replaced."""

import pytest

from cinta.cli import main
from cinta.core import media, models, whisper
from cinta.errors import CintaError


@pytest.fixture
def fake_transcription(monkeypatch, tmp_path):
    """Stands in for the two external tools and the model download.

    Writing the transcripts is what whisper-cli would do, so the command's own
    behaviour - where it puts them, what it skips, what it reports - runs for
    real against real files.
    """
    calls: dict = {"transcribed": [], "fail_on": set()}

    monkeypatch.setenv("CINTA_MODELS_DIR", str(tmp_path / "models"))
    (tmp_path / "models").mkdir()
    for model in models.ALL:
        (tmp_path / "models" / model.filename).write_bytes(b"model")

    monkeypatch.setattr(media, "extract_audio", lambda source, destination: destination.touch())

    def fake_run(arguments):
        stem = arguments[arguments.index("-of") + 1]
        audio = arguments[arguments.index("-f") + 1]
        if any(name in audio for name in calls["fail_on"]):
            raise CintaError("whisper-cli failed: unreadable audio")
        calls["transcribed"].append(stem)
        for path in whisper.outputs_for(__import__("pathlib").Path(stem)):
            path.write_text("transcript")

    monkeypatch.setattr(whisper, "run", fake_run)
    return calls


def test_transcripts_land_beside_the_file_they_describe(fake_transcription, tmp_path):
    """You chose where the video lives; its transcript belongs in the same
    folder, not collected into ~/cinta away from it."""
    source = tmp_path / "lectures" / "week1.mp4"
    source.parent.mkdir()
    source.write_bytes(b"video")

    assert main(["transcribe", str(source)]) == 0
    assert (tmp_path / "lectures" / "week1.txt").exists()
    assert (tmp_path / "lectures" / "week1.srt").exists()


def test_output_dir_collects_them_elsewhere(fake_transcription, tmp_path):
    source = tmp_path / "week1.mp4"
    source.write_bytes(b"video")
    destination = tmp_path / "transcripts"

    assert main(["transcribe", str(source), "--output-dir", str(destination)]) == 0
    assert (destination / "week1.txt").exists()


def test_an_already_transcribed_file_is_skipped(fake_transcription, tmp_path):
    """Re-running over a folder after adding one file must not spend an hour
    redoing the rest."""
    source = tmp_path / "week1.mp4"
    source.write_bytes(b"video")
    (tmp_path / "week1.txt").write_text("done earlier")

    assert main(["transcribe", str(source)]) == 0
    assert fake_transcription["transcribed"] == []


def test_force_transcribes_it_again(fake_transcription, tmp_path):
    source = tmp_path / "week1.mp4"
    source.write_bytes(b"video")
    (tmp_path / "week1.txt").write_text("done earlier")

    assert main(["transcribe", str(source), "--force"]) == 0
    assert len(fake_transcription["transcribed"]) == 1


def test_one_bad_file_does_not_abandon_the_rest(fake_transcription, tmp_path, capsys):
    """The whole point of transcribing a folder overnight: a corrupt file in the
    middle must not throw away the work done on the others. The exit code still
    reports that something failed."""
    good_one = tmp_path / "good1.mp4"
    broken = tmp_path / "broken.mp4"
    good_two = tmp_path / "good2.mp4"
    for path in (good_one, broken, good_two):
        path.write_bytes(b"video")
    fake_transcription["fail_on"].add("broken")

    assert main(["transcribe", str(good_one), str(broken), str(good_two)]) == 1

    assert (tmp_path / "good1.txt").exists()
    assert (tmp_path / "good2.txt").exists()
    assert not (tmp_path / "broken.txt").exists()
    assert "broken.mp4" in capsys.readouterr().err


def test_a_missing_input_is_reported_before_any_work(fake_transcription, tmp_path):
    """Loading a 3 GB model and then discovering the file was a typo wastes a
    minute for nothing."""
    assert main(["transcribe", str(tmp_path / "nope.mp4")]) != 0
    assert fake_transcription["transcribed"] == []


def test_stdout_lists_the_transcripts_written(fake_transcription, tmp_path, capsys):
    """Same contract as record: stdout is the paths, so the output can be piped."""
    source = tmp_path / "week1.mp4"
    source.write_bytes(b"video")

    assert main(["transcribe", str(source)]) == 0
    assert capsys.readouterr().out.split() == [
        str(tmp_path / "week1.txt"),
        str(tmp_path / "week1.srt"),
    ]
