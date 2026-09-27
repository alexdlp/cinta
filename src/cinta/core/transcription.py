"""Turning one media file into a transcript.

Shared by `cinta transcribe`, `cinta download --transcribe` and
`cinta record --transcribe`, which differ only in where the media came from.
"""

import tempfile
from pathlib import Path

from . import media, models, whisper


def transcribe(source: Path, output_stem: Path, language: str = "auto") -> list[Path]:
    available = models.ensure_available()
    output_stem.parent.mkdir(parents=True, exist_ok=True)

    # The 16 kHz mono WAV is an intermediate nobody asked for, so it lives in a
    # temporary directory and disappears even when the transcription fails.
    with tempfile.TemporaryDirectory(prefix="cinta-") as scratch:
        audio = Path(scratch) / (source.stem + ".wav")
        media.extract_audio(source, audio)
        whisper.run(
            whisper.transcribe_arguments(
                audio=audio,
                output_stem=output_stem,
                model=available[models.SPEECH.filename],
                vad_model=available[models.VAD.filename],
                language=language,
            )
        )

    return whisper.outputs_for(output_stem)
