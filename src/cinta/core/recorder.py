"""Client for the cintarec JSON contract (DESIGN.md 5.5).

Everything user-friendly happens here: cintarec only understands indices and
ids, so names are resolved to those before it is invoked.
"""

import re
from datetime import datetime
from pathlib import Path

from ..errors import CintaError
from ..external import run_recorder


def list_targets() -> dict:
    return run_recorder(["--list"])


def _resolve(spec: str | None, items: list[dict], kind: str) -> dict:
    """Accepts a number (the index shown by `cinta devices`), an id, or part of a name.

    Names are what people actually remember, so 'monitor' is a valid way to say
    'Mi Monitor'.
    """
    if not items:
        raise CintaError(f"No {kind}s are available.")

    if spec is None:
        return next(
            (item for item in items if item.get("isDefault") or item.get("isMain")), items[0]
        )

    if spec.isdigit():
        index = int(spec)
        match = next((item for item in items if item["index"] == index), None)
        if match:
            return match

    for item in items:
        if str(item["id"]) == spec or f"id:{item['id']}" == spec:
            return item

    lowered = spec.casefold()
    matches = [item for item in items if lowered in item["name"].casefold()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(item["name"] for item in matches)
        raise CintaError(
            f"'{spec}' matches more than one {kind}: {names}.",
            exit_code=12,
            hint="Use the number shown by: cinta devices",
        )

    available = "\n".join(f"  {item['index']}  {item['name']}" for item in items)
    raise CintaError(
        f"There is no {kind} matching '{spec}'. Available:\n{available}",
        exit_code=12,
        hint="Run: cinta devices",
    )


def resolve_display(spec: str | None, displays: list[dict]) -> dict:
    return _resolve(spec, displays, "display")


def resolve_microphone(spec: str | None, microphones: list[dict]) -> dict:
    return _resolve(spec, microphones, "microphone")


def slugify(name: str) -> str:
    """Filenames keep the display name readable but lose anything that travels
    badly across filesystems."""
    collapsed = re.sub(r"\s+", "", name.strip())
    return re.sub(r"[^\w-]", "", collapsed) or "screen"


def output_path(directory: Path, display_name: str, when: datetime | None = None) -> Path:
    """<YYYY-MM-DD>-<HHMMSS>-<display>.mov, date first so ls sorts by time."""
    stamp = (when or datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    return directory / f"{stamp}-{slugify(display_name)}.mov"


def record(
    *,
    output: Path,
    display: dict,
    microphone: dict | None,
    audio: str,
    duration: float | None,
    fps: int,
    scale: float,
    show_cursor: bool,
    codec: str,
) -> dict:
    arguments = [
        "--output",
        str(output),
        "--display",
        f"id:{display['id']}",
        "--audio",
        audio,
        "--fps",
        str(fps),
        "--scale",
        str(scale),
        "--codec",
        codec,
    ]
    if microphone is not None:
        arguments += ["--mic", f"id:{microphone['id']}"]
    if duration is not None:
        arguments += ["--duration", str(duration)]
    if not show_cursor:
        arguments.append("--no-cursor")

    return run_recorder(arguments)
