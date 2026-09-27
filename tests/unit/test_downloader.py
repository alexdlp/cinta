"""The yt-dlp command line."""

from pathlib import Path

import pytest

from cinta.core import downloader


def build(**overrides):
    arguments = {
        "url": "https://example.com/video",
        "kind": "audio",
        "output_dir": Path("/out"),
        "paths_file": Path("/tmp/paths"),
    }
    arguments.update(overrides)
    return downloader.download_arguments(**arguments)


def value_after(arguments, flag):
    return arguments[arguments.index(flag) + 1]


def test_the_written_paths_are_asked_for_not_guessed():
    """The old script predicted output names by reimplementing yt-dlp's
    post-processing rules, and got them wrong whenever yt-dlp changed. Asking
    for after_move:filepath is the whole fix: it is the name on disk once
    everything, including the mp3 conversion, has finished."""
    arguments = build()
    index = arguments.index("--print-to-file")
    assert arguments[index + 1] == "after_move:filepath"
    assert arguments[index + 2] == "/tmp/paths"


def test_audio_becomes_mp3_at_the_best_quality():
    arguments = build(kind="audio")
    assert "--extract-audio" in arguments
    assert value_after(arguments, "--audio-format") == "mp3"
    assert value_after(arguments, "--audio-quality") == "0"


def test_video_is_merged_into_mp4():
    arguments = build(kind="video")
    assert value_after(arguments, "--merge-output-format") == "mp4"
    assert value_after(arguments, "--format") == downloader.VIDEO_FORMAT


def test_compatible_prefers_h264_but_still_falls_back():
    """QuickTime cannot play VP9 or AV1, which is what --compatible is for. The
    chain has to end in the generic selector: preferring H.264 must never turn
    into failing when only VP9 exists."""
    arguments = build(kind="video", compatible=True)
    selector = value_after(arguments, "--format")
    assert "avc1" in selector
    assert selector.endswith(downloader.VIDEO_FORMAT)


def test_a_single_video_does_not_drag_in_its_playlist():
    """A course URL usually sits inside a playlist of two hundred lessons."""
    assert "--no-playlist" in build()
    assert "--no-playlist" not in build(playlist=True)


def test_titles_are_truncated_so_the_filename_survives():
    """Filesystems cap a name at 255 bytes, and a YouTube title can exceed it."""
    assert "%(title).80s.%(ext)s" in value_after(build(), "--output")


def test_local_urls_are_enabled_only_when_one_is_given():
    """yt-dlp disables file:// by default so that a URL from an untrusted source
    cannot read the disk. Typing one is a different matter."""
    assert "--enable-file-urls" in build(url="file:///tmp/clip.mp4")
    assert "--enable-file-urls" not in build(url="https://example.com/video")


def test_an_explicit_selector_replaces_the_defaults():
    assert value_after(build(selector="worst"), "--format") == "worst"


@pytest.mark.parametrize("kind", ["audio", "video"])
def test_the_url_goes_last(kind):
    """Anything after the URL would be read as another URL."""
    assert build(kind=kind)[-1] == "https://example.com/video"
