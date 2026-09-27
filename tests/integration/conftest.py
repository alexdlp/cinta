"""Real tools, real models, no doubles.

These run ffmpeg, whisper-cli and yt-dlp exactly as a user's machine would,
with the same large-v3 and Silero models cinta always uses. If the models are
not on disk yet, the first test downloads them, as the first transcription
would.

The media is generated here rather than committed: macOS speaks a known
sentence, so a test can check that the right words come back. A tone would not
do - voice-activity detection correctly finds no speech in it.
"""

import subprocess
from pathlib import Path

import pytest

SENTENCE = "The quick brown fox jumps over the lazy dog."


def words(text: str) -> str:
    return " ".join("".join(c for c in text.lower() if c.isalpha() or c.isspace()).split())


@pytest.fixture(scope="session")
def media(tmp_path_factory) -> dict[str, Path]:
    directory = tmp_path_factory.mktemp("media")
    speech = directory / "speech.aiff"
    # The voice is named because the default follows the system language: on a
    # Spanish Mac it reads the English sentence with Spanish phonetics, and
    # Whisper rightly hears "home sober de" for "jumps over the".
    subprocess.run(["say", "-v", "Samantha", "-o", str(speech), SENTENCE], check=True)

    audio = directory / "spoken-audio.m4a"
    video = directory / "spoken-video.mp4"
    ffmpeg = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    subprocess.run([*ffmpeg, "-i", str(speech), "-c:a", "aac", str(audio)], check=True)
    subprocess.run(
        [
            *ffmpeg,
            "-f", "lavfi", "-i", "color=c=black:s=320x240:r=10",
            "-i", str(speech),
            "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(video),
        ],
        check=True,
    )  # fmt: skip

    # Different names on purpose: two inputs sharing a stem would share a
    # transcript, and the second would be skipped as already transcribed.
    broken = directory / "broken.mp4"
    broken.write_bytes(b"this is not a video")
    return {"audio": audio, "video": video, "broken": broken}


def duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout)
