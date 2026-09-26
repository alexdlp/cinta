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


def models_dir() -> Path:
    """Where the Whisper models live.

    whisper.cpp has no location of its own - its -m default is a cwd-relative
    path left over from running inside the source tree - so cinta picks one.
    It sits under the output directory because cinta owns these files' whole
    life: it downloads them, replaces them when it wants a different model, and
    removes them on request.
    """
    from_env = os.environ.get("CINTA_MODELS_DIR")
    if from_env:
        return Path(from_env).expanduser()
    return output_dir() / "models"


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
