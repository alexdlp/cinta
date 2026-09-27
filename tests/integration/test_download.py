"""cinta download through the real yt-dlp, from a file:// URL: the whole
pipeline, without depending on YouTube or the network."""

from pathlib import Path

import pytest

from cinta.cli import main

from .conftest import SENTENCE, duration, words

pytestmark = pytest.mark.integration


def written_paths(capsys) -> list[Path]:
    return [Path(line) for line in capsys.readouterr().out.splitlines() if line]


def test_video_by_default(media, tmp_path, capsys):
    exit_code = main(["download", media["video"].as_uri(), "--output-dir", str(tmp_path)])

    assert exit_code == 0
    [video] = written_paths(capsys)
    assert video.parent == tmp_path
    assert video.suffix == ".mp4"
    assert duration(video) == pytest.approx(duration(media["video"]), abs=0.2)


def test_audio_only_as_mp3(media, tmp_path, capsys):
    exit_code = main(
        ["download", media["video"].as_uri(), "--audio", "--output-dir", str(tmp_path)]
    )

    assert exit_code == 0
    [audio] = written_paths(capsys)
    assert audio.suffix == ".mp3"
    assert duration(audio) > 1


def test_download_and_transcribe_land_in_one_folder(media, tmp_path, capsys):
    exit_code = main(
        ["download", media["video"].as_uri(), "--transcribe", "--output-dir", str(tmp_path)]
    )

    assert exit_code == 0
    paths = written_paths(capsys)
    assert {path.suffix for path in paths} == {".mp4", ".txt", ".srt"}
    folder = paths[0].parent
    assert folder.parent == tmp_path
    assert all(path.parent == folder for path in paths)

    transcript = next(path for path in paths if path.suffix == ".txt")
    assert words(SENTENCE) in words(transcript.read_text())
