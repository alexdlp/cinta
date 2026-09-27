"""yt-dlp, driven as a subprocess.

Keeping it out of the Python process is what lets the Homebrew formula declare
`depends_on "yt-dlp"` instead of pinning ten transitive Python dependencies that
change every week (DESIGN.md 6.3). YouTube breaks yt-dlp often enough that
`brew upgrade yt-dlp` fixing it without touching cinta is the whole point.
"""

from pathlib import Path

from ..external import run_tool_relaying

# Best video plus best audio, falling back to whatever single file exists.
VIDEO_FORMAT = "bv*+ba/best"

# H.264 in MP4, which QuickTime and Finder previews can play without help. Each
# step is a fallback for the one before, ending in the generic selector: a
# download never fails just because the compatible variant is missing.
COMPATIBLE_VIDEO_FORMAT = (
    "bv*[vcodec^=avc1][ext=mp4]+ba[ext=m4a]/"
    "bv*[vcodec^=avc1][ext=mp4]+ba[ext=mp4]/"
    "b[vcodec^=avc1][ext=mp4]/" + VIDEO_FORMAT
)

# 80 characters of title: long enough to recognise, short enough to survive
# filesystems that cap a name at 255 bytes once the extension is added.
OUTPUT_TEMPLATE = "%(title).80s.%(ext)s"


def download_arguments(
    *,
    url: str,
    kind: str,
    output_dir: Path,
    paths_file: Path,
    playlist: bool = False,
    compatible: bool = False,
    selector: str | None = None,
) -> list[str]:
    # A playlist is one job that produces many files, so they go into a folder
    # named after it. yt-dlp fills in the title and creates the directory.
    template = f"%(playlist_title)s/{OUTPUT_TEMPLATE}" if playlist else OUTPUT_TEMPLATE

    arguments = [
        "--output",
        str(output_dir / template),
        # Where the real output paths come back from. The alternative is to
        # predict them by reimplementing yt-dlp's post-processing rules, which
        # is what the old script did and what broke whenever yt-dlp changed.
        # after_move is the name on disk once everything has finished.
        "--print-to-file",
        "after_move:filepath",
        str(paths_file),
    ]

    if url.startswith("file://"):
        # yt-dlp refuses local URLs by default, because a URL arriving from
        # somewhere untrusted could then read the disk. Here the user typed it,
        # and it is what makes testing the pipeline without the network possible.
        arguments.append("--enable-file-urls")

    if not playlist:
        # A single video URL that happens to sit in a playlist should download
        # the one video, not the other two hundred.
        arguments.append("--no-playlist")
    if kind == "audio":
        arguments += [
            "--format",
            selector or "bestaudio/best",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
        ]
    else:
        arguments += [
            "--format",
            selector or (COMPATIBLE_VIDEO_FORMAT if compatible else VIDEO_FORMAT),
            "--merge-output-format",
            "mp4",
        ]

    arguments.append(url)
    return arguments


def download(**kwargs) -> list[Path]:
    """Run yt-dlp and return what it actually wrote."""
    paths_file = kwargs["paths_file"]
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    paths_file.write_text("")

    run_tool_relaying("yt-dlp", download_arguments(**kwargs))

    return [Path(line) for line in paths_file.read_text().splitlines() if line.strip()]
