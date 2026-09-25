"""ffmpeg argument construction. Snapshot-style: these catch flag regressions
without running ffmpeg at all."""

from pathlib import Path

from cinta.core import media


def test_mix_copies_the_video_instead_of_re_encoding():
    """Re-encoding an hour of 3440x1440 to change the audio would cost minutes
    and a generation of quality, for nothing."""
    arguments = media.mix_arguments(Path("/in.mov"), Path("/out.mov"))
    assert arguments[arguments.index("-c:v") + 1] == "copy"


def test_mix_does_not_halve_the_volume():
    """amix normalizes by default: it divides every input by the number of
    sources, so a mix of two tracks comes out at half the level of either."""
    arguments = media.mix_arguments(Path("/in.mov"), Path("/out.mov"))
    assert "normalize=0" in arguments[arguments.index("-filter_complex") + 1]


def test_mix_takes_both_audio_tracks_and_the_video():
    """The whole point: one video stream plus both audio tracks in, one audio
    track out. Dropping a map would silently lose the microphone."""
    arguments = media.mix_arguments(Path("/in.mov"), Path("/out.mov"))
    filter_graph = arguments[arguments.index("-filter_complex") + 1]
    assert "[0:a:0][0:a:1]" in filter_graph
    assert "0:v:0" in arguments
    assert arguments[-1] == "/out.mov"
