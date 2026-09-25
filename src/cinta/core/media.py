"""ffmpeg work: everything that happens to a file after it is written."""

from pathlib import Path

from ..external import run_tool


def mix_arguments(source: Path, destination: Path) -> list[str]:
    """Collapse the two audio tracks of a recording into one.

    cintarec writes system audio and microphone as separate tracks, because
    mixing inside Swift would mean an AVAudioEngine with resampling. The cost of
    leaving them separate is that players sound both at once: the microphone
    hears the speakers a few milliseconds late, and the two combine into audible
    comb filtering. So they are mixed here, where ffmpeg already is.

    normalize=0 keeps the original levels; ffmpeg's default would divide every
    input by the number of sources and halve the volume of both.
    """
    return [
        "-y",
        "-v",
        "error",
        "-i",
        str(source),
        "-filter_complex",
        "[0:a:0][0:a:1]amix=inputs=2:duration=longest:normalize=0[mixed]",
        "-map",
        "0:v:0",
        "-map",
        "[mixed]",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(destination),
    ]


def mix_audio_tracks(path: Path) -> None:
    """Mix in place. ffmpeg cannot edit a file it is reading, so this goes
    through a sibling and then replaces the original."""
    scratch = path.with_name(path.stem + ".mixing" + path.suffix)
    try:
        run_tool("ffmpeg", mix_arguments(path, scratch))
        scratch.replace(path)
    finally:
        scratch.unlink(missing_ok=True)
