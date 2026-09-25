"""Parsing '30s', '5m', '1h30m' into seconds."""

import re

from .errors import CintaError

_PATTERN = re.compile(
    r"^(?:(?P<hours>\d+(?:\.\d+)?)h)?"
    r"(?:(?P<minutes>\d+(?:\.\d+)?)m)?"
    r"(?:(?P<seconds>\d+(?:\.\d+)?)s)?$"
)

EXAMPLES = "Examples: 30s, 5m, 1h30m."


def parse_duration(text: str) -> float:
    """Seconds, from a string that must say its unit.

    A bare number is refused rather than guessed at: '15' could reasonably mean
    fifteen seconds or fifteen minutes, the two differ by a factor of sixty, and
    the caller is about to leave the recording unattended. The error names the
    two spellings, so the format is learned once.
    """
    raw = text.strip().casefold()

    try:
        float(raw)
    except ValueError:
        pass
    else:
        raise CintaError(
            f"'{text}' does not say its unit.",
            exit_code=2,
            hint=f"Write {raw}s for seconds, {raw}m for minutes or {raw}h for hours.",
        )

    match = _PATTERN.fullmatch(raw)
    if not match or not any(match.groups()):
        raise CintaError(f"'{text}' is not a duration.", exit_code=2, hint=EXAMPLES)

    hours, minutes, seconds = (float(value or 0) for value in match.groups())
    total = hours * 3600 + minutes * 60 + seconds
    if total <= 0:
        raise CintaError(f"'{text}' is not a duration longer than zero.", exit_code=2)
    return total
