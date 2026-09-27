"""cinta transcribe - turn media into text, from a file or from a URL."""

import argparse
import tempfile
from pathlib import Path

from .. import config
from ..core import downloader, layout, transcription, whisper
from ..errors import CintaError
from ..ui import say


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "transcribe",
        help="Transcribe audio or video into text",
        description="Transcribe media into a .txt and a .srt. Give it files you already "
        "have, or a URL to fetch. Runs entirely on this machine.",
    )
    parser.add_argument("sources", nargs="+", metavar="FILE|URL", help="What to transcribe")
    parser.add_argument(
        "--lang",
        default="auto",
        help="Spoken language, as a code like 'es' or 'en'. The default detects it "
        "from the first seconds, which occasionally gets it wrong.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="For a URL, keep the downloaded audio instead of discarding it",
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
    urls = [source for source in args.sources if layout.looks_like_url(source)]
    files = [source for source in args.sources if not layout.looks_like_url(source)]

    if urls and files:
        raise CintaError(
            "Give either files or a URL, not both in the same command.",
            exit_code=2,
        )
    if len(urls) > 1:
        raise CintaError("One URL at a time.", exit_code=2)

    if urls:
        return transcribe_url(urls[0], args)
    return transcribe_files([Path(path).expanduser() for path in files], args)


def transcribe_url(url: str, args: argparse.Namespace) -> int:
    """Audio only: Whisper needs the sound, and the video is ten times the size
    for nothing. `cinta download --transcribe` is the command for keeping the
    video as well."""
    destination = config.output_dir(args.output_dir)

    with tempfile.TemporaryDirectory(prefix="cinta-") as scratch:
        say("Fetching the audio")
        downloaded = downloader.download(
            url=url,
            kind="audio",
            output_dir=Path(scratch),
            paths_file=Path(scratch) / "paths",
        )
        if not downloaded:
            raise CintaError("Nothing was downloaded from that URL.")

        media_file = downloaded[0]

        # Keeping the audio means the job now produces media and a transcript,
        # which by the layout rule belong together in a folder.
        if args.keep:
            folder = layout.job_folder(destination, media_file.stem)
            kept = folder / media_file.name
            media_file.replace(kept)
            media_file = kept
            stem = folder / media_file.stem
        else:
            stem = destination / media_file.stem
            stem.parent.mkdir(parents=True, exist_ok=True)

        say(media_file.stem)
        written = transcription.transcribe(media_file, stem, args.lang)

    if args.keep:
        print(media_file)
    for path in written:
        print(path)
    return 0


def transcribe_files(inputs: list[Path], args: argparse.Namespace) -> int:
    missing = [path for path in inputs if not path.is_file()]
    if missing:
        raise CintaError("No such file: " + ", ".join(str(path) for path in missing))

    failures: list[tuple[Path, str]] = []
    written: list[Path] = []

    for index, source in enumerate(inputs, start=1):
        stem = output_stem(source, args.output_dir)
        if any(path.exists() for path in whisper.outputs_for(stem)) and not args.force:
            say(f"[{index}/{len(inputs)}] {source.name}: already transcribed, skipping")
            continue

        say(f"[{index}/{len(inputs)}] {source.name}")
        try:
            written.extend(transcription.transcribe(source, stem, args.lang))
        except CintaError as error:
            # One unreadable file must not abandon the rest of a long batch.
            say(f"  failed: {error.message}")
            failures.append((source, error.message))

    for path in written:
        print(path)

    if failures:
        say("")
        say(f"{len(failures)} of {len(inputs)} failed:")
        for source, reason in failures:
            say(f"  {source.name}: {reason}")
        return 1
    return 0


def output_stem(source: Path, output_dir: str | None) -> Path:
    """Transcripts land beside the file they describe.

    You chose where that file lives; scattering its transcript into ~/cinta
    would separate the two. --output-dir overrides it.
    """
    directory = Path(output_dir).expanduser() if output_dir else source.parent
    return directory / source.stem
