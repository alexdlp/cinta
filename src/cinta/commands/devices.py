"""cinta devices - what there is to record from."""

import argparse
import json

from ..core import recorder


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "devices",
        help="List the screens and microphones available",
        description="List what cinta can record from.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    targets = recorder.list_targets()

    if args.json:
        print(json.dumps(targets, indent=2, ensure_ascii=False))
        return 0

    show(targets)
    return 0


def show(targets: dict) -> None:
    print("Screens")
    for display in targets["displays"]:
        marker = "  (main)" if display["isMain"] else ""
        print(
            f"  {display['index']}  {display['name']:<26} "
            f"{display['pixelWidth']}x{display['pixelHeight']}{marker}"
        )

    print("\nMicrophones")
    if not targets["microphones"]:
        print("  none found")
    for microphone in targets["microphones"]:
        marker = "  (default)" if microphone["isDefault"] else ""
        print(f"  {microphone['index']}  {microphone['name']}{marker}")

    # Windows and applications are deliberately not shown. cintarec enumerates
    # them, and --json still carries them, but recording a single window is not
    # implemented yet - listing targets that cannot be recorded is worse than
    # listing nothing.

    if targets["displays"]:
        example = targets["displays"][0]
        print(f"\nRecord with:  cinta record --display {example['index']}")
        print(f"Or by name:   cinta record --display '{example['name']}'")
