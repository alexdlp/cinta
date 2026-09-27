"""What the Python layer and cintarec must agree on, read from both sides.

Neither side can check this alone: the Swift tests do not know which codes
Python explains, and the Python tests only ever talk to a double of cintarec.
"""

import re
import tomllib
from pathlib import Path

from cinta import __version__
from cinta.errors import RECORDER_EXIT_CODES

ROOT = Path(__file__).resolve().parents[2]
SWIFT_SOURCES = ROOT / "swift" / "cintarec" / "Sources" / "cintarec"


def test_every_failure_cintarec_can_report_has_an_explanation():
    source = (SWIFT_SOURCES / "Exit.swift").read_text()
    codes = {int(code) for code in re.findall(r"case \w+ = (\d+)", source)}
    assert codes - {0} == set(RECORDER_EXIT_CODES)


def test_one_version_everywhere():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    swift = re.search(r'cintarecVersion = "([^"]+)"', (SWIFT_SOURCES / "main.swift").read_text())
    assert pyproject["project"]["version"] == __version__ == swift.group(1)
