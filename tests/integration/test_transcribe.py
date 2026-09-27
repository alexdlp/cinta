"""cinta transcribe against real media, with the real models."""

import pytest

from cinta.cli import main

from .conftest import SENTENCE, words

pytestmark = pytest.mark.integration


def test_audio_and_video_come_out_as_the_words_spoken(media, tmp_path):
    exit_code = main(
        ["transcribe", str(media["audio"]), str(media["video"]), "--output-dir", str(tmp_path)]
    )

    assert exit_code == 0
    for stem in ("spoken-audio", "spoken-video"):
        transcript = (tmp_path / f"{stem}.txt").read_text()
        assert words(SENTENCE) in words(transcript)

        subtitles = (tmp_path / f"{stem}.srt").read_text()
        assert "-->" in subtitles
        assert "quick brown fox" in subtitles.lower()


def test_a_broken_file_fails_alone(media, tmp_path, capsys):
    exit_code = main(
        ["transcribe", str(media["broken"]), str(media["audio"]), "--output-dir", str(tmp_path)]
    )

    assert exit_code != 0
    assert "broken.mp4" in capsys.readouterr().err
    assert not (tmp_path / "broken.txt").exists()
    assert words(SENTENCE) in words((tmp_path / "spoken-audio.txt").read_text())
