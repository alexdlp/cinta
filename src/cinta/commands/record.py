"""cinta record - record a screen, with audio, to a file you can find."""

import argparse
import json
import sys
from pathlib import Path

from .. import config
from ..core import layout, media, recorder, transcription
from ..duration import parse_duration
from ..errors import CintaError
from ..ui import human_duration, human_size, say


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "record",
        help="Record a screen, with system audio and/or microphone",
        description="Record a screen. With no options it records the main display, "
        "along with the sound your Mac is playing, until you press Enter.",
    )
    parser.add_argument(
        "duration",
        nargs="?",
        metavar="DURATION",
        help="How long to record: 30s, 5m, 1h30m. Omit to record until Ctrl-C.",
    )
    parser.add_argument(
        "--display",
        metavar="SCREEN",
        help="Screen to record: its number from `cinta devices`, or part of its "
        "name (for example: 'monitor'). Default: the main display.",
    )
    parser.add_argument(
        "--mic",
        metavar="DEVICE",
        help="Microphone to record: its number from `cinta devices`, or part of "
        "its name. Only used with --audio mic or --audio both. Default: whichever "
        "input macOS is set to use.",
    )
    parser.add_argument(
        "--audio",
        choices=("system", "mic", "both", "none"),
        default="system",
        help="What to record alongside the video. 'system' is the sound your Mac "
        "is playing, 'mic' is your microphone, 'both' mixes the two into one track. "
        "Default: system.",
    )
    parser.add_argument("--output", metavar="FILE", help="Write to this exact path")
    parser.add_argument("--output-dir", metavar="DIR", help="Write into this directory")
    parser.add_argument("--fps", type=int, default=30, help="Frames per second. Default: 30.")
    parser.add_argument(
        "--scale", type=float, default=1.0, help="Scale the output down, 0-1. Default: 1."
    )
    parser.add_argument("--no-cursor", action="store_true", help="Do not draw the mouse pointer")
    parser.add_argument(
        "--codec", choices=("h264", "hevc"), default="h264", help="Video codec. Default: h264."
    )
    parser.add_argument("--force", action="store_true", help="Overwrite the output if it exists")
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Transcribe the recording when it finishes, leaving the video and "
        "the transcript together in one folder",
    )
    parser.add_argument(
        "--keep-tracks",
        action="store_true",
        help="With --audio both, leave system audio and microphone as separate "
        "tracks instead of mixing them into one",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    seconds = parse_duration(args.duration) if args.duration else None

    targets = recorder.list_targets()
    display = recorder.resolve_display(args.display, targets["displays"])
    microphone = None
    if args.audio in ("mic", "both"):
        microphone = recorder.resolve_microphone(args.mic, targets["microphones"])

    if args.output:
        output = Path(args.output).expanduser()
    elif args.transcribe:
        # The video and its transcript are several files from one job, so the
        # folder is created before recording starts, while the name is known.
        directory = config.output_dir(args.output_dir)
        stem = recorder.output_name(display["name"])
        output = layout.job_folder(directory, stem) / f"{stem}.mov"
    else:
        directory = config.output_dir(args.output_dir)
        output = recorder.output_path(directory, display["name"])

    if output.exists():
        if not args.force:
            raise CintaError(
                f"{output} already exists.", exit_code=13, hint="Pass --force to overwrite it."
            )
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    say(f"Screen:    {display['name']} ({display['pixelWidth']}x{display['pixelHeight']})")
    say(f"Audio:     {describe_audio(args.audio, microphone)}")
    say(f"Saving to: {output}")

    def started(event: dict) -> None:
        # Said now, not before launching cintarec: until the first frame is
        # written ScreenCaptureKit is still starting, and anything that plays in
        # that second is not in the file.
        if args.json:
            print(json.dumps(event, ensure_ascii=False), flush=True)
        say(f"Recording. {how_to_stop(args.duration)}")

    report = recorder.record(
        output=output,
        display=display,
        microphone=microphone,
        audio=args.audio,
        duration=seconds,
        fps=args.fps,
        scale=args.scale,
        show_cursor=not args.no_cursor,
        codec=args.codec,
        on_started=started,
    )
    say()

    if args.audio == "both" and not args.keep_tracks:
        say("Mixing system audio and microphone...")
        media.mix_audio_tracks(output)
        report["bytes"] = output.stat().st_size
        report["audioTracks"] = [{"kind": "mixed", "channels": 2}]

    transcripts: list[Path] = []
    if args.transcribe:
        say("")
        say("Transcribing the recording...")
        try:
            transcripts = transcription.transcribe(output, output.with_suffix(""))
        except CintaError as error:
            # The recording is not repeatable; a failure in the second step must
            # not take the first one down with it.
            say(f"error: {error.message}")
            say("")
            say(f"The recording itself is safe: {output}")
            say(f"Transcribe it later with:  cinta transcribe {output}")
            return error.exit_code

    if args.json:
        # One line per event, so a program can read stdout as it arrives:
        # "started" when recording begins, "finished" with the report.
        print(json.dumps({"event": "finished", **report}, ensure_ascii=False))
    else:
        say(f"Recorded {human_duration(report['durationSeconds'])}, {human_size(report['bytes'])}")
        print(report["path"])
        for path in transcripts:
            print(path)
    return 0


def how_to_stop(duration: str | None) -> str:
    # Enter only works with a terminal on stdin; under a program, the way to
    # stop is a signal.
    interactive = sys.stdin.isatty()
    if duration:
        return f"Stopping after {duration}" + (
            ", or press Enter to stop sooner." if interactive else "."
        )
    return "Press Enter to stop." if interactive else "Send SIGINT or SIGTERM to stop."


def describe_audio(mode: str, microphone: dict | None) -> str:
    if mode == "none":
        return "none"
    if mode == "system":
        return "system audio"
    if mode == "mic":
        return f"microphone ({microphone['name']})"
    return f"system audio + microphone ({microphone['name']})"
