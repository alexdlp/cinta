# cinta

**Capture audio and video on your Mac, and turn it into text.**

`cinta` is a single command-line tool that covers the whole path from "there is something I
want" to "here is the file, and here is the transcript".

There are two ways in and one way out:

| | Command | What you get |
|---|---|---|
| **From the internet** | `cinta download <url>` | Audio or video from any site `yt-dlp` supports — YouTube, Vimeo, course platforms, podcasts |
| **From your own screen** | `cinta record` | A screen recording, with system audio and/or your microphone |
| **As text** | `cinta transcribe <files\|url>` | A transcript of anything above, or of media you already have |

```bash
cinta download "https://youtu.be/VIDEO"                # the video, into ~/cinta
cinta devices                                          # what you can record from
cinta record --display 'Mi Monitor' 5m                 # 5 minutes of screen + system audio
cinta transcribe ~/lectures/*.mp4                      # transcribe them, locally
cinta transcribe "https://youtu.be/VIDEO"              # fetch the audio, keep only the text
cinta record --transcribe                              # record, then transcribe it
```

Two things that follow from the design and are worth knowing before you install it:

- **Transcription runs on your machine.** `whisper.cpp` works offline; no audio is uploaded
  anywhere, and there is no API key and no per-minute cost.
- **Screen recording needs no extra software.** No virtual audio device to install: system
  audio is captured through Apple's ScreenCaptureKit. macOS 13 or newer.

## Install

```bash
brew tap alexdlp/tap
brew trust alexdlp/tap
brew install cinta
```

The first two lines are needed once. The install downloads the Whisper models (3.1 GB), so it
takes a few minutes; after that nothing is fetched on first use. `brew uninstall cinta`
removes all of it, models included, and leaves only what you recorded, downloaded or
transcribed.

Recording the screen needs one permission, and macOS gives it to your terminal rather than to
cinta: System Settings > Privacy & Security > Screen & System Audio Recording, enable your
terminal, then restart it.

The design is in [DESIGN.md](DESIGN.md).

## Development

The project language is English: code, comments, docs, commit messages and user-facing output.

```bash
uv sync                    # creates .venv with the uv-managed CPython 3.13
make build-swift           # builds the screen recorder (once)
uv run cinta devices       # run the CLI
make test                  # the fast tests
make test-swift            # the recorder's tests
uv run pytest -m integration   # real ffmpeg, whisper-cli, yt-dlp and models
uv run pytest -m recording     # records the screen for real; needs the permission
make fmt                   # ruff format + ruff check --fix
```

`uv tool install --editable .` puts `cinta` on your PATH if you would rather not type
`uv run` every time.
