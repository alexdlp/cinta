"""cinta transcribe - turn media you already have into text."""

import argparse
import tempfile
from pathlib import Path

from ..core import media, models, whisper
from ..errors import CintaError
from ..ui import say


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio or video into text",
        description="Transcribe media into a .txt and a .srt, next to the original file. "
        "Runs entirely on this machine.",
    )
    parser.add_argument("paths", nargs="+", metavar="FILE", help="Files to transcribe")
    parser.add_argument(
        "--lang",
        default="auto",
        help="Spoken language, as a code like 'es' or 'en'. The default detects it "
        "from the first seconds, which occasionally gets it wrong.",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        help="Write the transcripts here instead of beside each input file",
    )
    parser.add_argument(
        "--force", action="store_true", help="Transcribe again even if a transcript exists"
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    inputs = [Path(path).expanduser() for path in args.paths]
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise CintaError("No such file: " + ", ".join(str(path) for path in missing))

    available = models.ensure_available()
    speech = available[models.SPEECH.filename]
    vad = available[models.VAD.filename]

    failures: list[tuple[Path, str]] = []
    written: list[Path] = []

    for index, source in enumerate(inputs, start=1):
        stem = output_stem(source, args.output_dir)
        existing = [path for path in whisper.outputs_for(stem) if path.exists()]
        if existing and not args.force:
            say(f"[{index}/{len(inputs)}] {source.name}: already transcribed, skipping")
            continue

        say(f"[{index}/{len(inputs)}] {source.name}")
        try:
            transcribe_one(source, stem, speech, vad, args.lang)
        except CintaError as error:
            # One unreadable file must not abandon the rest of a long batch.
            say(f"  failed: {error.message}")
            failures.append((source, error.message))
            continue
        written.extend(whisper.outputs_for(stem))

    for path in written:
        print(path)

    if failures:
        say("")
        say(f"{len(failures)} of {len(inputs)} failed:")
        for source, reason in failures:
            say(f"  {source.name}: {reason}")
        return 1
    return 0


def transcribe_one(source: Path, stem: Path, speech: Path, vad: Path, language: str) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)

    # The WAV is an intermediate nobody asked for, so it lives in a temporary
    # directory and disappears even if the transcription fails.
    with tempfile.TemporaryDirectory(prefix="cinta-") as scratch:
        audio = Path(scratch) / (source.stem + ".wav")
        media.extract_audio(source, audio)
        whisper.run(
            whisper.transcribe_arguments(
                audio=audio, output_stem=stem, model=speech, vad_model=vad, language=language
            )
        )


def output_stem(source: Path, output_dir: str | None) -> Path:
    """Transcripts land beside the file they describe.

    You chose where that file lives; scattering its transcript into ~/cinta
    would separate the two. --output-dir overrides it when you want them
    collected somewhere.
    """
    directory = Path(output_dir).expanduser() if output_dir else source.parent
    return directory / source.stem
