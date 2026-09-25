"""Human-facing output. Data goes to stdout, progress and errors go to stderr."""

import sys


def say(message: str = "") -> None:
    print(message, file=sys.stderr)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def human_duration(seconds: float) -> str:
    minutes, remainder = divmod(int(round(seconds)), 60)
    if minutes:
        return f"{minutes}m {remainder:02d}s"
    return f"{remainder}s"
