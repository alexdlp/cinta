"""The only module that spawns subprocesses. Tests replace this layer, not what
is underneath it."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import RECORDER_EXIT_CODES, CintaError

RECORDER_NAME = "cintarec"


def tool_path(name: str) -> Path:
    """Locate an external tool without trusting PATH blindly (DESIGN.md 7.6).

    A conda or pyenv install earlier on PATH would otherwise shadow the one
    Homebrew installed as a dependency of cinta.
    """
    from_env = os.environ.get(f"CINTA_{name.upper().replace('-', '_')}")
    if from_env:
        candidate = Path(from_env).expanduser()
        if candidate.is_file():
            return candidate
        raise CintaError(f"$CINTA_{name.upper()} points at {candidate}, which is not a file.")

    brew_prefix = (
        Path("/opt/homebrew") if Path("/opt/homebrew/bin").is_dir() else Path("/usr/local")
    )
    in_brew = brew_prefix / "bin" / name
    if in_brew.is_file():
        return in_brew

    found = shutil.which(name)
    if found:
        return Path(found)

    raise CintaError(f"{name} is not installed.", hint=f"Run: brew install {name}")


def run_tool(name: str, arguments: list[str]) -> None:
    """Run an external tool that produces no data on stdout."""
    result = subprocess.run(
        [str(tool_path(name)), *arguments], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        tail = detail[-1] if detail else f"exit code {result.returncode}"
        raise CintaError(f"{name} failed: {tail}")


def recorder_path() -> Path:
    """cintarec is an implementation detail, never on the user's PATH. Homebrew
    installs it into libexec and points $CINTA_RECORDER at it; in a source
    checkout it is wherever swift build left it."""
    from_env = os.environ.get("CINTA_RECORDER")
    if from_env:
        candidate = Path(from_env).expanduser()
        if candidate.is_file():
            return candidate
        raise CintaError(
            f"$CINTA_RECORDER points at {candidate}, which is not a file.",
            exit_code=13,
        )

    beside_us = Path(sys.argv[0]).resolve().parent / RECORDER_NAME
    if beside_us.is_file():
        return beside_us

    in_checkout = (
        Path(__file__).resolve().parents[2]
        / "swift"
        / "cintarec"
        / ".build"
        / "release"
        / RECORDER_NAME
    )
    if in_checkout.is_file():
        return in_checkout

    found = shutil.which(RECORDER_NAME)
    if found:
        return Path(found)

    raise CintaError(
        "The screen recorder is not built.",
        exit_code=13,
        hint="Run: make build-swift",
    )


def run_recorder(arguments: list[str]) -> dict:
    """Run cintarec and return its JSON report.

    stdout is the data channel and carries the report. stderr is cintarec's own
    log: it is captured rather than shown, because the user-facing narration is
    this layer's job, and surfaced only when something goes wrong.
    """
    command = [str(recorder_path()), *arguments]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        stdout, stderr = process.communicate()
    except KeyboardInterrupt:
        # Ctrl-C reaches cintarec too, and it needs to finish writing the file
        # rather than be killed: an unfinished .mov has no moov atom and will not
        # play. So wait for it instead of tearing it down.
        stdout, stderr = process.communicate()

    if process.returncode != 0:
        message, hint = RECORDER_EXIT_CODES.get(
            process.returncode, (f"The recorder failed (exit code {process.returncode}).", None)
        )
        detail = (stderr or "").strip()
        if detail and process.returncode not in RECORDER_EXIT_CODES:
            message = f"{message}\n{detail}"
        raise CintaError(message, exit_code=process.returncode, hint=hint)

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as error:
        raise CintaError(f"The recorder returned output that is not JSON: {error}") from error
