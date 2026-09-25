"""Durations always say their unit."""

import pytest

from cinta.duration import parse_duration
from cinta.errors import CintaError


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("30s", 30),
        ("5m", 300),
        ("1h", 3600),
        ("1h30m", 5400),
        ("1h30m15s", 5415),
        ("90s", 90),
        ("1.5m", 90),
        ("5M", 300),
        ("  2m  ", 120),
    ],
)
def test_accepts_seconds_minutes_and_hours(text, seconds):
    assert parse_duration(text) == seconds


def test_a_bare_number_is_refused_with_both_spellings():
    """'15' could be fifteen seconds or fifteen minutes, sixty times apart, and
    the recording is about to be left unattended. Guessing is worse than asking."""
    with pytest.raises(CintaError) as error:
        parse_duration("15")
    assert "15s" in error.value.hint
    assert "15m" in error.value.hint


@pytest.mark.parametrize("text", ["", "abc", "5x", "m", "30 s", "1m2h"])
def test_nonsense_is_rejected(text):
    with pytest.raises(CintaError):
        parse_duration(text)


@pytest.mark.parametrize("text", ["0s", "0m", "0h"])
def test_zero_is_not_a_duration(text):
    with pytest.raises(CintaError):
        parse_duration(text)
