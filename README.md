# cinta

**Capture audio and video on your Mac, and turn it into text.**

`cinta` is a single command-line tool that covers the whole path from "there is something I
want" to "here is the file, and here is the transcript". It replaces a pile of shell scripts,
OBS, and hand-run `ffmpeg` invocations.

There are two ways in and one way out:

| | Command | What you get |
|---|---|---|
| **From the internet** | `cinta download <url>` | Audio or video from any site `yt-dlp` supports — YouTube, Vimeo, course platforms, podcasts |
| **From your own screen** | `cinta record` | A screen recording, with system audio and/or your microphone |
| **As text** | `cinta transcribe <url>`<br>`cinta batch <files>` | A transcript of anything above, or of media you already have |

```bash
cinta download "https://youtu.be/VIDEO" --type video   # a video file in ~/cinta
cinta devices                                          # what you can record from
cinta record --display 'Mi Monitor' 5m                 # 5 minutes of screen + system audio
cinta transcribe "https://youtu.be/VIDEO"              # download it and write the transcript
cinta batch ~/lectures/*.mp4                           # transcribe a folder you already have
cinta models download large-v3                         # fetch the transcription model
```

Two things that follow from the design and are worth knowing before you install it:

- **Transcription runs on your machine.** `whisper.cpp` works offline; no audio is uploaded
  anywhere, and there is no API key and no per-minute cost.
- **Screen recording needs no extra software.** No OBS, no BlackHole, no virtual audio device.
  System audio is captured through Apple's ScreenCaptureKit. macOS 13 or newer.

> **Status: in development.** The design is settled and written down in [DESIGN.md](DESIGN.md);
> the commands above are being implemented one at a time. Nothing is installable yet.

## Development

The project language is English: code, comments, docs, commit messages and user-facing output.

```bash
uv sync                    # creates .venv with the uv-managed CPython 3.13
make build-swift           # builds the screen recorder (once)
uv run cinta devices       # run the CLI
make test                  # pytest
make fmt                   # ruff format + ruff check --fix
```

`uv tool install --editable .` puts `cinta` on your PATH if you would rather not type
`uv run` every time.
