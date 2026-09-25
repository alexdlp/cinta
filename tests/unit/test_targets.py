"""Resolving what the user typed into a display or a microphone."""

from datetime import datetime

import pytest

from cinta.core import recorder
from cinta.errors import CintaError

DISPLAYS = [
    {"index": 1, "id": 2, "name": "Mi Monitor", "isMain": False},
    {"index": 2, "id": 3, "name": "ARZOPA", "isMain": False},
    {"index": 3, "id": 1, "name": "Built-in Retina Display", "isMain": True},
]

MICROPHONES = [
    {
        "index": 1,
        "id": "BuiltInMicrophoneDevice",
        "name": "MacBook Pro Microphone",
        "isDefault": True,
    },
    {"index": 2, "id": "USB-Audio", "name": "Yeti Stereo Microphone", "isDefault": False},
]


def test_number_is_an_index_not_an_id():
    """The case that motivated the two spellings: on this arrangement index 1 and
    id 1 are different screens, and the bare number must mean the index."""
    assert recorder.resolve_display("1", DISPLAYS)["name"] == "Mi Monitor"
    assert recorder.resolve_display("id:1", DISPLAYS)["name"] == "Built-in Retina Display"


def test_resolves_by_partial_name_case_insensitively():
    """Nobody remembers that ARZOPA is number 2. They remember it is the ARZOPA."""
    assert recorder.resolve_display("arzopa", DISPLAYS)["index"] == 2
    assert recorder.resolve_display("Mi Mon", DISPLAYS)["index"] == 1


def test_default_display_is_the_main_one():
    """Pins the documented default (DESIGN.md 4.4). Changing it silently would
    start recording a different screen for everyone who passes no --display."""
    assert recorder.resolve_display(None, DISPLAYS)["isMain"] is True


def test_default_microphone_is_the_system_default():
    """Same contract for inputs: no --mic means whatever macOS is set to use."""
    assert recorder.resolve_microphone(None, MICROPHONES)["isDefault"] is True


def test_ambiguous_name_is_refused_rather_than_guessed():
    with pytest.raises(CintaError) as error:
        recorder.resolve_display("o", DISPLAYS)
    assert "more than one" in error.value.message


def test_unknown_target_lists_what_is_available():
    """A typo must produce the list of real options and exit code 12, not a
    stack trace: the exit code is what the Homebrew formula and any script see."""
    with pytest.raises(CintaError) as error:
        recorder.resolve_display("portatil", DISPLAYS)
    assert error.value.exit_code == 12
    assert "Mi Monitor" in error.value.message


def test_empty_list_is_an_error():
    """No screens at all (a headless machine, a disconnected session) must fail
    rather than index into an empty list."""
    with pytest.raises(CintaError):
        recorder.resolve_display(None, [])


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Mi Monitor", "MiMonitor"),
        ("Built-in Retina Display", "Built-inRetinaDisplay"),
        ("LG/UltraFine 5K", "LGUltraFine5K"),
        ("   ", "screen"),
    ],
)
def test_slugify_keeps_names_readable_but_portable(name, expected):
    """Display names reach the filesystem verbatim otherwise. A slash would
    create a directory, and an all-whitespace name an unnamed file."""
    assert recorder.slugify(name) == expected


def test_output_path_is_sortable_by_time(tmp_path):
    """The naming contract from DESIGN.md 4.0: date first, so that ls orders
    recordings chronologically instead of alphabetically by screen."""
    when = datetime(2026, 9, 18, 17, 16, 28)
    path = recorder.output_path(tmp_path, "Mi Monitor", when)
    assert path.name == "2026-09-18-171628-MiMonitor.mov"
    assert path.parent == tmp_path
