"""Root parser and subcommand dispatch."""

import argparse
import sys

from . import __version__
from .commands import devices, download, record, transcribe
from .errors import CintaError
from .ui import say


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cinta",
        description="Capture audio and video on your Mac, and turn it into text.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument("--version", action="version", version=f"cinta {__version__}")

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    devices.add_parser(subparsers)
    download.add_parser(subparsers)
    record.add_parser(subparsers)
    transcribe.add_parser(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "handler", None):
        parser.print_help()
        return 2

    try:
        return args.handler(args)
    except CintaError as error:
        say(f"error: {error.message}")
        if error.hint:
            say("")
            say(error.hint)
        return error.exit_code
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
