"""Building the whisper-cli command line.

The flag set is the profile that used to be hardcoded in a bash wrapper. It is
kept because it is tuned, not because it is default: whisper-cli's own defaults
produce worse transcripts on long recordings.
"""

import re
import subprocess
import sys
from collections import deque
from pathlib import Path

from ..errors import CintaError
from ..external import tool_path

# Whisper only accepts a handful of audio formats and works internally at
# 16 kHz mono, so everything is converted before it gets here.
AUDIO_FORMATS = {".wav", ".mp3", ".flac", ".ogg"}


def transcribe_arguments(
    *,
    audio: Path,
    output_stem: Path,
    model: Path,
    vad_model: Path,
    language: str = "auto",
) -> list[str]:
    return [
        "-m",
        str(model),
        "-f",
        str(audio),
        "-of",
        str(output_stem),
        # Voice activity detection. Without it Whisper hallucinates through
        # silence; 0.7 is stricter than the 0.5 default and cuts more of it.
        "--vad",
        "--vad-model",
        str(vad_model),
        "--vad-threshold",
        "0.7",
        # Auto-detection reads the first 30 seconds. --lang overrides it for the
        # recordings that open with music or with jargon from another language.
        "-l",
        language,
        # Greedy decoding. Sampling invents more than it fixes on lecture audio.
        "--temperature",
        "0",
        # No context carried between segments: it is what makes Whisper repeat
        # itself for minutes once it slips.
        "-mc",
        "0",
        # Drop "(music)", "(applause)" and friends.
        "-sns",
        # Segments short enough to read as subtitles.
        "--max-len",
        "192",
        "-pp",
        "-otxt",
        "-osrt",
    ]


def outputs_for(output_stem: Path) -> list[Path]:
    """The files whisper-cli will write, given -of."""
    return [output_stem.with_suffix(".txt"), output_stem.with_suffix(".srt")]


SEGMENT = re.compile(r"^\[\d{2}:\d{2}:\d{2}")
PROGRESS = re.compile(r"progress\s*=\s*(\d+)%")
LANGUAGE = re.compile(r"auto-detected language: (\S+)")


def run(arguments: list[str]) -> None:
    """Run whisper-cli, showing the useful part of its output and hiding the rest.

    Two reasons this cannot just inherit the terminal. whisper-cli writes its
    transcript to *stdout*, which would land in the middle of cinta's own stdout
    where only file paths belong. And it writes about 150 lines of backend and
    timing detail to stderr for a ten-second clip, which buries the one line
    anybody wants to see.

    So both streams are read here, the transcript and the progress are echoed to
    stderr as they arrive, and the rest is kept only in case the run fails.
    """
    process = subprocess.Popen(
        [str(tool_path("whisper-cli")), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    recent: deque[str] = deque(maxlen=20)
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        recent.append(line)

        if SEGMENT.match(line):
            print(f"  {line}", file=sys.stderr, flush=True)
            continue

        language = LANGUAGE.search(line)
        if language:
            print(f"  language: {language.group(1)}", file=sys.stderr, flush=True)
            continue

        progress = PROGRESS.search(line)
        if progress and sys.stderr.isatty():
            print(f"\r  {progress.group(1)}%", end="", file=sys.stderr, flush=True)

    if process.wait() != 0:
        detail = "\n".join(recent)
        raise CintaError(f"whisper-cli failed:\n{detail}")
