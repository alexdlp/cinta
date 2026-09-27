"""cinta download - pull audio or video off the internet."""

import argparse
import tempfile
from pathlib import Path

from .. import config
from ..core import downloader, layout, transcription
from ..errors import CintaError
from ..ui import say


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "download",
        help="Download audio or video from a URL",
        description="Download media from any site yt-dlp supports.",
    )
    parser.add_argument("url", help="The page holding the media")
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Download only the audio, as MP3, instead of the video",
    )
    parser.add_argument("--output-dir", metavar="DIR", help="Write here instead of ~/cinta")
    parser.add_argument(
        "--playlist",
        action="store_true",
        help="Download the whole playlist when the URL is part of one",
    )
    parser.add_argument(
        "--compatible",
        action="store_true",
        help="Prefer H.264/MP4, which QuickTime plays without help",
    )
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Transcribe it as well, leaving the media and the transcript together",
    )
    parser.add_argument(
        "--format",
        metavar="SELECTOR",
        dest="selector",
        help="Pass a raw yt-dlp format selector, bypassing the defaults",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    destination = config.output_dir(args.output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    kind = "audio" if args.audio else "video"
    say(f"Downloading {kind} to {destination}")

    with tempfile.TemporaryDirectory(prefix="cinta-") as scratch:
        written = downloader.download(
            url=args.url,
            kind=kind,
            output_dir=destination,
            paths_file=Path(scratch) / "paths",
            playlist=args.playlist,
            compatible=args.compatible,
            selector=args.selector,
        )

    if not written:
        raise CintaError(
            "yt-dlp finished without writing anything.",
            hint="The media may already be downloaded, or the URL may hold no media.",
        )

    if args.transcribe:
        written = transcribe_each(written, destination, playlist=args.playlist)

    for path in written:
        print(path)
    return 0


def transcribe_each(media_files: list, destination, *, playlist: bool) -> list:
    """Media plus transcript is several files from one job, so they go into a
    folder together. A playlist already has one - yt-dlp made it - so the
    transcripts simply join their media there."""
    results = []
    for index, media_file in enumerate(media_files, start=1):
        if playlist:
            target = media_file
        else:
            folder = layout.job_folder(destination, media_file.stem)
            target = folder / media_file.name
            media_file.replace(target)

        say(f"[{index}/{len(media_files)}] {target.stem}")
        results.append(target)
        results.extend(transcription.transcribe(target, target.with_suffix("")))
    return results
