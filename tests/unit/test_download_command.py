"""cinta download, with yt-dlp replaced."""

import pytest

from cinta.cli import main
from cinta.core import downloader


@pytest.fixture
def fake_yt_dlp(monkeypatch, tmp_path):
    """Writes the paths file the way yt-dlp's --print-to-file would."""
    calls: dict = {"produced": ["clip.mp3"]}

    def fake_run(name, arguments):
        assert name == "yt-dlp"
        calls["arguments"] = arguments
        destination = arguments[arguments.index("--output") + 1]
        directory = tmp_path / "written"
        directory.mkdir(exist_ok=True)
        paths_file = arguments[arguments.index("--print-to-file") + 2]
        with open(paths_file, "w") as handle:
            for name_ in calls["produced"]:
                path = directory / name_
                path.write_bytes(b"media")
                handle.write(f"{path}\n")
        calls["output_template"] = destination

    monkeypatch.setattr(downloader, "run_tool_relaying", fake_run)
    return calls


def test_downloads_land_in_the_output_directory(fake_yt_dlp, monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "cinta"))
    assert main(["download", "https://example.com/v"]) == 0
    assert str(tmp_path / "cinta") in fake_yt_dlp["output_template"]


def test_stdout_lists_what_was_written(fake_yt_dlp, monkeypatch, tmp_path, capsys):
    """This is what makes `cinta transcribe $(cinta download URL)` work, and it
    only holds if yt-dlp's progress output never reaches our stdout."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "cinta"))
    fake_yt_dlp["produced"] = ["one.mp3", "two.mp3"]

    assert main(["download", "https://example.com/playlist", "--playlist"]) == 0

    printed = capsys.readouterr().out.split()
    assert [line.rsplit("/", 1)[-1] for line in printed] == ["one.mp3", "two.mp3"]


def test_downloading_nothing_is_an_error(fake_yt_dlp, monkeypatch, tmp_path):
    """yt-dlp exits zero when it skips a file it already has. Reporting success
    with no path would leave anything reading that output with nothing."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "cinta"))
    fake_yt_dlp["produced"] = []
    assert main(["download", "https://example.com/v"]) != 0


def test_video_is_what_you_get_unless_you_ask_otherwise(fake_yt_dlp, monkeypatch, tmp_path):
    """Downloading is for keeping the thing; audio is the special case, asked
    for with --audio."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "cinta"))
    assert main(["download", "https://example.com/v"]) == 0

    arguments = fake_yt_dlp["arguments"]
    assert "--merge-output-format" in arguments
    assert "--extract-audio" not in arguments


def test_the_audio_flag_switches_to_mp3(fake_yt_dlp, monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "cinta"))
    assert main(["download", "https://example.com/v", "--audio"]) == 0

    arguments = fake_yt_dlp["arguments"]
    assert "--extract-audio" in arguments
    assert arguments[arguments.index("--audio-format") + 1] == "mp3"
