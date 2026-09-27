"""The Whisper models: one speech model, one voice-activity model.

There is no catalogue and no choice. whisper.cpp ships no models at all - the
Homebrew formula says as much in its caveats and points at a web page - and the
download script that makes this painless lives in the source repository, which
Homebrew does not install. So cinta does what that script did: two fixed URLs.
"""

import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..errors import CintaError
from ..ui import human_size, say


@dataclass(frozen=True)
class Model:
    filename: str
    url: str
    approximate_bytes: int
    description: str


# large-v3 is the most accurate Whisper model. Pinned here rather than chosen at
# runtime: when a better one appears, this constant changes and cinta fetches it.
SPEECH = Model(
    filename="ggml-large-v3.bin",
    url="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
    approximate_bytes=3_095_000_000,
    description="speech recognition",
)

# Without voice-activity detection Whisper invents text during silence: it
# repeats the previous line or produces phantom sentences. This model marks
# which parts of the audio contain speech so the rest is skipped.
VAD = Model(
    filename="ggml-silero-v5.1.2.bin",
    url="https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin",
    approximate_bytes=886_000,
    description="voice activity detection",
)

ALL = (SPEECH, VAD)


def path_for(model: Model) -> Path:
    return config.models_dir() / model.filename


def ensure_available(models=ALL) -> dict[str, Path]:
    """Return the path of each model, downloading the ones that are missing."""
    return {model.filename: _ensure_one(model) for model in models}


def _ensure_one(model: Model) -> Path:
    target = path_for(model)
    if target.is_file():
        return target

    say(f"Downloading the {model.description} model ({human_size(model.approximate_bytes)}).")
    say("This happens once.")
    download(model, target)
    return target


def download(model: Model, target: Path) -> None:
    """Resumable download.

    The speech model is about 3 GB. A transfer that dies at 80% and restarts
    from zero is not acceptable, so bytes land in a .part file that is resumed
    with a Range request and only renamed once complete.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    already = partial.stat().st_size if partial.exists() else 0

    request = urllib.request.Request(model.url)
    if already:
        request.add_header("Range", f"bytes={already}-")
        say(f"Resuming at {human_size(already)}.")

    try:
        with urllib.request.urlopen(request) as response:
            # A server that ignores the Range header replies 200 with the whole
            # file; appending to what we have would corrupt it.
            if already and response.status != 206:
                already = 0
                partial.unlink(missing_ok=True)

            total = _expected_total(response, already)
            mode = "ab" if already else "wb"
            with partial.open(mode) as handle:
                _copy_with_progress(response, handle, already, total)
    except urllib.error.URLError as error:
        raise CintaError(
            f"Could not download {model.filename}: {error.reason}",
            hint="The partial download is kept; running the command again resumes it.",
        ) from error

    partial.replace(target)
    say(f"Saved to {target}")


def _expected_total(response, already: int) -> int:
    length = response.headers.get("Content-Length")
    return already + int(length) if length else 0


def _copy_with_progress(response, handle, already: int, total: int) -> None:
    chunk_size = 1024 * 1024
    written = already
    last_report = 0.0

    while True:
        chunk = response.read(chunk_size)
        if not chunk:
            break
        handle.write(chunk)
        written += len(chunk)

        # One line, rewritten in place, and only when there is a terminal to
        # rewrite: piped output should not collect thousands of progress lines.
        if total and os.isatty(2):
            fraction = written / total
            if fraction - last_report >= 0.01:
                last_report = fraction
                print(
                    f"\r  {fraction:5.1%}  {human_size(written)} of {human_size(total)}",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )
    if total and os.isatty(2):
        print("", file=sys.stderr)
