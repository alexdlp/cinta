"""Where output goes (DESIGN.md 4.0).

One directory for everything the tool produces, because a single run can emit
several files and splitting them by type would scatter one job's results.
"""

import os
import tomllib
from pathlib import Path

CONFIG_FILE = Path.home() / ".config" / "cinta" / "config.toml"
DEFAULT_OUTPUT_DIR = Path.home() / "cinta"


def load_config() -> dict:
    if not CONFIG_FILE.is_file():
        return {}
    try:
        with CONFIG_FILE.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def output_dir(override: str | Path | None = None) -> Path:
    """--output-dir, then $CINTA_OUTPUT_DIR, then config.toml, then ~/cinta."""
    if override:
        return Path(override).expanduser()

    from_env = os.environ.get("CINTA_OUTPUT_DIR")
    if from_env:
        return Path(from_env).expanduser()

    configured = load_config().get("output_dir")
    if configured:
        return Path(str(configured)).expanduser()

    return DEFAULT_OUTPUT_DIR
