"""The only module that spawns subprocesses. Tests replace this layer, not what
is underneath it."""

import json
import os
import shutil
import subprocess
import sys
from collections import deque
from pathlib import Path

from .errors import RECORDER_EXIT_CODES, CintaError

RECORDER_NAME = "cintarec"

# The binary and the formula that provides it are not always called the same
# thing, and the error message has to name the one you can actually install.
FORMULA_FOR = {"whisper-cli": "whisper.cpp"}


def tool_path(name: str) -> Path:
    """Locate an external tool without trusting PATH blindly (DESIGN.md 6.6).

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

    raise CintaError(
        f"{name} is not installed.", hint=f"Run: brew install {FORMULA_FOR.get(name, name)}"
    )


def run_tool_relaying(name: str, arguments: list[str]) -> None:
    """Run a tool whose progress should be visible, sending all of it to stderr.

    These tools write to stdout: yt-dlp puts its progress bar there. Letting
    them inherit the terminal would mix that into cinta's own stdout, where only
    file paths belong, and anything reading those paths would get a screenful of
    progress instead.

    Relayed as raw chunks rather than lines because progress bars are built from
    carriage returns with no newline: splitting on lines would show nothing until
    the download finished.
    """
    process = subprocess.Popen(
        [str(tool_path(name)), *arguments], stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    tail: deque[bytes] = deque(maxlen=64)

    assert process.stdout is not None
    descriptor = process.stdout.fileno()
    while True:
        chunk = os.read(descriptor, 4096)
        if not chunk:
            break
        sys.stderr.buffer.write(chunk)
        sys.stderr.buffer.flush()
        tail.append(chunk)

    if process.wait() != 0:
        detail = b"".join(tail).decode(errors="replace").strip().splitlines()
        raise CintaError(
            f"{name} failed.\n" + "\n".join(detail[-5:]) if detail else f"{name} failed."
        )


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
