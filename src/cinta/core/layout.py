"""Where the files of one job end up (DESIGN.md 3.0).

The rule: one file stays loose in the output directory, several files from the
same job go into a folder named after it. Twenty recordings that were also
transcribed would otherwise be sixty loose files.

The `.txt` and `.srt` pair counts as one result. They are the same transcript in
two formats, they share a stem and they sort together, so a folder holding only
those two would be ceremony.
"""

from pathlib import Path


def job_folder(base: Path, stem: str) -> Path:
    folder = base / stem
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def looks_like_url(argument: str) -> bool:
    return argument.startswith(("http://", "https://", "file://"))
