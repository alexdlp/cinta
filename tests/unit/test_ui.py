"""Number formatting for humans."""

import pytest

from cinta.ui import human_duration, human_size


@pytest.mark.parametrize(
    ("value", "expected"),
    [(512, "512 B"), (2048, "2 KB"), (5 * 1024 * 1024, "5.0 MB"), (3 * 1024**3, "3.0 GB")],
)
def test_sizes_are_scaled_to_a_readable_unit(value, expected):
    """A recording reported as 26214400 bytes tells you nothing at a glance."""
    assert human_size(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"), [(5, "5s"), (59, "59s"), (60, "1m 00s"), (3725, "62m 05s")]
)
def test_durations_are_split_into_minutes_and_seconds(value, expected):
    """Same for '3725 seconds'. The zero padding keeps a column of them aligned."""
    assert human_duration(value) == expected
