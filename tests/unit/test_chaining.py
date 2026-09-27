"""Recording or downloading and transcribing in one command."""

import pytest

from cinta.cli import main
from cinta.core import downloader, layout, transcription
from cinta.errors import CintaError


@pytest.fixture
def fake_transcriber(monkeypatch):
    """Replaces the transcription step, writing the files it would write."""
    calls: dict = {"sources": [], "fail": False}

    def fake(source, output_stem, language="auto"):
        if calls["fail"]:
            raise CintaError("whisper-cli failed")
        calls["sources"].append(source)
        written = [output_stem.with_suffix(".txt"), output_stem.with_suffix(".srt")]
        for path in written:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("transcript")
        return written

    monkeypatch.setattr(transcription, "transcribe", fake)
    return calls


def test_a_recording_and_its_transcript_share_a_folder(fake_recorder, fake_transcriber, tmp_path):
    """Three files from one job. Twenty such jobs loose in ~/cinta would be
    sixty files; in folders they are twenty entries."""
    assert (
        main(["record", "--display", "1", "--transcribe", "--output-dir", str(tmp_path), "2s"]) == 0
    )

    recording = fake_recorder["record"]["output"]
    assert recording.parent.parent == tmp_path
    assert recording.parent.name == recording.stem
    assert (recording.parent / f"{recording.stem}.txt").exists()


def test_a_recording_without_transcription_stays_loose(fake_recorder, tmp_path):
    """One file needs no folder around it."""
    assert main(["record", "--display", "1", "--output-dir", str(tmp_path), "2s"]) == 0
    assert fake_recorder["record"]["output"].parent == tmp_path


def test_a_failed_transcription_does_not_cost_you_the_recording(
    fake_recorder, fake_transcriber, tmp_path, capsys
):
    """A recording is not repeatable. If the second step fails the first must
    survive, the exit code must say something went wrong, and the message must
    say how to retry just the transcription."""
    fake_transcriber["fail"] = True

    exit_code = main(
        ["record", "--display", "1", "--transcribe", "--output-dir", str(tmp_path), "2s"]
    )

    assert exit_code != 0
    recording = fake_recorder["record"]["output"]
    assert recording.exists()
    assert "cinta transcribe" in capsys.readouterr().err


def test_downloading_with_transcription_groups_them_too(monkeypatch, fake_transcriber, tmp_path):
    def fake_run(name, arguments):
        paths_file = arguments[arguments.index("--print-to-file") + 2]
        media = tmp_path / "lesson.mp3"
        media.write_bytes(b"audio")
        open(paths_file, "w").write(f"{media}\n")

    monkeypatch.setattr(downloader, "run_tool_relaying", fake_run)

    assert (
        main(["download", "https://example.com/v", "--transcribe", "--output-dir", str(tmp_path)])
        == 0
    )
    assert (tmp_path / "lesson" / "lesson.mp3").exists()
    assert (tmp_path / "lesson" / "lesson.txt").exists()


def test_a_url_and_files_together_are_refused():
    """Not a technical limit, a deliberate one: the two behave differently
    enough - one downloads, the others do not - that mixing them in a single
    command invites surprises."""
    assert main(["transcribe", "clip.mp4", "https://example.com/v"]) == 2


def test_only_one_url_at_a_time():
    assert main(["transcribe", "https://example.com/a", "https://example.com/b"]) == 2


@pytest.mark.parametrize(
    ("argument", "is_url"),
    [
        ("https://youtu.be/x", True),
        ("http://example.com/x", True),
        ("file:///tmp/x.mp4", True),
        ("/Users/me/clip.mp4", False),
        ("clip.mp4", False),
    ],
)
def test_telling_a_url_from_a_path(argument, is_url):
    assert layout.looks_like_url(argument) is is_url
