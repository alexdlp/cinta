# Design: `cinta` — a macOS command-line suite for recording, downloading and transcribing media

> Design document. Status: the repository is initialized (uv project, package skeleton, test
> layout). None of the commands are implemented yet.
> Decisions made: distribution through a **Homebrew tap**, a single **`cinta` CLI with
> subcommands**, a Swift recorder capturing **video + audio**, **uv** as the project manager,
> and a scope of **devices + download + record + transcribe**.

## What `cinta` does

`cinta` captures audio and video on a Mac and turns it into text. There are two ways in and
one way out:

| | Command | What it gets you |
|---|---|---|
| **In, from the internet** | `cinta download` | Audio or video from any site `yt-dlp` supports |
| **In, from your own screen** | `cinta record` | A screen recording with system audio and/or microphone |
| **Out, as text** | `cinta transcribe` | A transcript of any media, local or remote |

Transcription runs on a Whisper model that cinta fetches by itself the first time it is
needed; there is nothing to install or choose.

Two properties worth stating up front, because they drive most of the design:

- **Transcription is local.** Audio never leaves the machine; `whisper.cpp` runs on-device.
- **There is no GUI and no daemon.** Every subcommand is a one-shot Unix tool: stdout carries
  data, stderr carries logs, the exit code means something.

---

## 1. Design principles

1. **One compiled binary.** The only thing that gets compiled is the Swift recorder. Everything
   else is pure Python.
2. **Zero Python runtime dependencies.** See §6: this turns the Homebrew formula into something
   that needs no maintenance when the external tools are updated. The only *build* dependency
   is `flit_core`, which has no transitive dependencies.
3. **External tools are Homebrew dependencies**, not vendored: `ffmpeg`, `yt-dlp`,
   `whisper.cpp`. Homebrew keeps them current.
4. **All external I/O goes through one thin layer** (`external.py`). Tests stub that layer, not
   anything below it.
5. **Stable output for machines, pretty output for humans.** `--json` on every subcommand; logs
   go to stderr, data goes to stdout.
6. **Fail early, with instructions.** If a model or a permission is missing, the error names the
   exact command that fixes it.
7. **The project language is English** — code, comments, docstrings, docs, commit messages and
   user-facing output.

---

## 2. Repository layout

```
cinta/
├── pyproject.toml              # flit_core build backend (§6.2)
├── README.md                   # user-facing
├── DESIGN.md                   # this document
├── LICENSE                     # MIT
├── Makefile                    # make build-swift / test / fmt
├── src/cinta/
│   ├── __init__.py             # __version__
│   ├── cli.py                  # root parser + subcommand dispatch
│   ├── config.py               # XDG paths, config.toml, environment variables
│   ├── duration.py             # '30s' / '5m' / '1h30m' -> seconds
│   ├── errors.py               # CintaError -> exit codes
│   ├── external.py             # THE ONLY place that spawns subprocesses
│   ├── ui.py                   # sizes, durations, stderr narration
│   ├── commands/
│   │   ├── devices.py
│   │   ├── download.py
│   │   ├── transcribe.py
│   │   └── record.py
│   └── core/
│       ├── downloader.py       # yt-dlp argv construction, reading back the paths
│       ├── layout.py           # one file loose, several files in a job folder
│       ├── media.py            # ffmpeg: to 16k mono WAV, track mixing
│       ├── transcription.py    # media file -> .txt + .srt, shared by all commands
│       ├── whisper.py          # whisper-cli argv + output filtering
│       ├── recorder.py         # client for the Swift binary (JSON contract)
│       └── models.py           # the two pinned models, resumable download
├── swift/cintarec/
│   ├── Package.swift           # swift-tools-version:5.9, .macOS(.v13)
│   ├── Info.plist              # NSMicrophoneUsageDescription (embedded)
│   ├── Sources/cintarec/
│   │   ├── main.swift          # entry point
│   │   ├── Options.swift       # hand-rolled argument parsing (no SPM deps)
│   │   ├── Shareable.swift     # SCShareableContent -> --list as JSON
│   │   ├── Microphone.swift    # input devices for --audio mic|both
│   │   ├── Recorder.swift      # SCStream + delegates
│   │   ├── Writer.swift        # AVAssetWriter (video + audio)
│   │   ├── Permissions.swift   # TCC preflight
│   │   ├── Exit.swift          # exit codes, part of the contract
│   │   └── Report.swift        # output JSON
│   └── Tests/cintarecTests/    # swift-testing: options, configuration, JSON shape
├── tests/
│   ├── unit/                   # no network, no real subprocesses
│   └── integration/            # real tools and models; also the by-hand recording test
├── uv.lock                     # lock file for the development dependencies
├── .python-version             # CPython managed by uv, not by conda
├── .github/workflows/ci.yml
└── packaging/homebrew/cinta.rb   # copied into the tap
```

---

## 3. The `cinta` CLI

A single entry point. `pyproject.toml` declares `cinta = "cinta.cli:main"`.

```
cinta [--json] <subcommand> ...

  devices                  List screens and microphones
  download    URL          Download audio or video
  transcribe  FILE... |URL Transcribe media into text
  record      [DURATION]   Record the screen
```

`--version` is a flag, not a subcommand.

**Durations always carry a unit**: `30s`, `5m`, `1h30m`. A bare number is refused rather than
interpreted. The two plausible readings of `15` are sixty times apart, and a duration is only
ever typed when the recording is about to be left unattended, so the error names both spellings
instead of guessing. The unit is parsed once in `duration.py` and every command that takes a
length of time uses it.

### 3.0 Where output goes and what it is called

**One destination directory for everything the tool produces: `~/cinta/`, flat.**

The reason it is not split by file type is that a single run produces several files.
`cinta transcribe URL` writes the media, the `.txt` and the `.srt`; `cinta record` may later
write a `.mov` plus a sidecar. Sending video to `~/Movies`, audio to `~/Music` and text to
`~/Documents` would tear one job's results across three folders. They share a filename stem
instead, which keeps them adjacent in any sorted listing.

Resolution order for the destination:

1. `--output FILE` — an exact path. Only for commands that produce exactly one file.
2. `--output-dir DIR`
3. `$CINTA_OUTPUT_DIR`
4. `output_dir` in `~/.config/cinta/config.toml`
5. `~/cinta/`, created on first use.

Naming contract:

| Command | Produces | Name |
|---|---|---|
| `download` | `.mp4` | `<title>.mp4`, the title from yt-dlp, sanitized |
| `download --audio` | `.mp3` | `<title>.mp3` |
| `record` | `.mov` | `<YYYY-MM-DD>-<HHMMSS>-<display>.mov` |
| `transcribe` | media + `.txt` + `.srt` | the media's stem, reused for the sidecars |
| `transcribe FILE` | `.txt` + `.srt` | the input's stem |

Rules that apply to all of them:

- **Date first** in generated names, so `ls` sorts chronologically.
- **Sanitization**: no `/`, no leading dots, whitespace collapsed, trailing dots and spaces
  trimmed (they break on other filesystems).
- **Never overwrite silently.** An existing destination is an error (exit code 13) unless
  `--force` is given.
- One job's outputs **share a stem**, and **a job that produces several files puts them in a
  folder** named after that stem. One file stays loose: a folder holding a single `.mp3` is
  ceremony. Twenty recordings that were also transcribed would otherwise be sixty loose files.

  The `.txt` and `.srt` pair counts as **one** result for this rule. They are the same
  transcript in two formats, share a stem and sort together, so `cinta transcribe URL` leaves
  them loose. A folder appears when there is media *and* a transcript, or when a playlist
  produces many files.

| Command | Produces | Layout |
|---|---|---|
| `record` | one `.mov` | loose |
| `record --transcribe` | `.mov` + `.txt` + `.srt` | folder |
| `download` | one file | loose |
| `download --playlist` | many files | folder, named by the playlist |
| `download --transcribe` | media + transcript | folder |
| `transcribe FILE` | `.txt` + `.srt` | beside the input |
| `transcribe URL` | `.txt` + `.srt` | loose |
| `transcribe URL --keep` | audio + transcript | folder |

Transcribing a local file is the exception to all of this: its `.txt` and `.srt` are written
beside the file itself, not into `~/cinta`. That folder was chosen by the user, and separating
a transcript from the video it describes helps nobody. `--output-dir` overrides it.

### 3.1 `cinta download`

```
cinta download URL [--audio] [--output-dir DIR] [--playlist]
                [--compatible] [--transcribe] [--format SELECTOR]
```

Video by default: downloading is for keeping the thing, and wanting only the sound is the
special case. `--audio` is that case, and produces an MP3 a tenth of the size. `--format` is an
escape hatch for passing a raw yt-dlp selector when the defaults are wrong.

**The written paths are asked for, not predicted.** Inferring them means reimplementing
yt-dlp's post-processing rules and getting them wrong the moment yt-dlp changes anything, so
yt-dlp is asked directly:

```
yt-dlp --print-to-file after_move:filepath PATHS_FILE ...
```

`after_move:filepath` is the name on disk once everything has finished, including the mp3
conversion that renames the file. Writing it to a *file* rather than to stdout matters:
**yt-dlp puts its progress bar on stdout**, so anything printed there arrives mixed into it.
The same trap caught `whisper-cli` (§5.1); both tools' output is relayed to stderr so that
cinta's stdout carries only paths, which is what makes this work:

```bash
cinta transcribe "$(cinta download URL)"
```

**No retry on an unavailable format.** Every selector chain already ends in `best`, so the
fallback happens inside yt-dlp. A failure that survives that would survive a retry too.

**`file://` URLs are enabled only when one is given.** yt-dlp refuses them by default, on the
grounds that a URL arriving from an untrusted source could then read the disk. A URL the user
typed is a different matter, and it is what makes the integration test in §7 possible without
the network.

### 3.2 `cinta transcribe`

```
cinta transcribe FILE... | URL  [--lang es|auto] [--keep] [--output-dir DIR] [--force]
```

Pipeline: (download, for a URL) → `ffmpeg` to 16 kHz mono WAV → `whisper-cli` → `.txt` and
`.srt`. There is no `--model`: there is one model (§5).

**Files or a URL, not both in one command**, and one URL at a time. Not a technical limit: the
two behave differently enough — one downloads first, the others do not — that mixing them in a
single command invites surprises. Several files at once is the case that matters, because
transcribing a course that was downloaded lesson by lesson is the main use, and a file that
fails in the middle of that must not discard the ones that already succeeded.

A URL downloads the **audio** only. Whisper needs the sound, and the video is ten times the
size for nothing. The audio is then discarded, because what was asked for is the text. `--keep`
keeps it, and since the job then produces media *and* a transcript, they go into a folder
together. Wanting the video as well is a different intent with its own command:
`cinta download --transcribe`.

### 3.3 `cinta record`

```
cinta record [DURATION] [--output FILE | --output-dir DIR]
          [--audio system|mic|both|none]   (default: system)
          [--display N|id:N] [--mic N|id:UID] [--app BUNDLE_ID] [--window ID]
          [--fps 30] [--scale 1] [--no-cursor] [--codec h264|hevc]
          [--list] [--json]
```

- With no `DURATION` it records until you **press Enter**. `Ctrl-C` also works and is equally
  safe, but asking someone to interrupt a process in order to end a recording normally is the
  wrong shape: interrupting should be the escape hatch, not the interface. `cintarec` watches
  stdin for this, and only when stdin is a terminal — piped input reaches EOF immediately, and
  treating that as a stop would end every scripted recording the instant it began.
- Listing capturable targets is **not** a flag of `record`: it is `cinta devices`, a top-level
  command. Screens and microphones are not the property of recording — anything else that
  captures will want them too — and a flag buried inside a subcommand is not where anyone looks
  for "what do I have". `cinta devices` shows screens and microphones, and nothing else.
  `cintarec --list` still emits windows and applications as JSON, and `cinta devices --json`
  passes them through, but the human listing omits them: recording a single window is not
  implemented, so showing dozens of windows would be offering targets that cannot be used. The
  listing comes back when `--window` and `--app` do.
- **Which display gets recorded.** One `SCStream` captures exactly one display: there is no
  "record everything". The default is the main display (`CGMainDisplayID()`, the one holding
  the menu bar), which is what `screencapture` does and the most predictable choice. It is a
  default, not a limitation — the development machine has three displays and the main one is
  the laptop panel, which is rarely the one being recorded. `--display 2` is the 1-based index
  from `cinta devices` (screens ordered left to right by desktop arrangement); `--display id:2`
  is the raw display id. The two spellings are deliberately different because they collide in
  practice: on the development machine index 1 and id 1 are different screens. Indices are
  renumbered when a monitor is plugged in, ids are not. Names come from
  `NSScreen.localizedName`; `SCDisplay` does not carry one.

## 4. The native recorder: `cintarec` (Swift + ScreenCaptureKit)

### 4.1 Why ScreenCaptureKit and nothing else

| Option | Verdict |
|---|---|
| **ScreenCaptureKit** | ✅ System audio **without drivers** (no BlackHole). Capture by display, window or app. Hardware encoding. Requires macOS 13. **Chosen.** |
| `screencapture -V` | Built into the system, but no system audio and no fine-grained control. Useful only as a fallback. |
| `ffmpeg -f avfoundation` | Needs a loopback device such as BlackHole for system audio, which means asking the user to install and configure a kernel extension. |

The development machine runs macOS 26.6.2 and Swift 6.4, so this is comfortable. The macOS 13
floor is there for other users, not for it.

### 4.2 Architecture of the binary

`cintarec` is a SwiftPM executable with **no external dependencies** (arguments parsed by hand,
no `swift-argument-parser`). Reason: Homebrew builds run in a sandbox with no network, and an
SPM dependency would have to be declared as a `resource` in the formula. Zero dependencies
means the formula compiles offline without ceremony.

```
main.swift
  └─ parse argv → Options
     ├─ --list  → Shareable.dump()  → JSON to stdout → exit
     └─ record  → Permissions.preflight()
                  → SCContentFilter (display | window | app)
                  → SCStreamConfiguration
                  → Recorder(stream) ──┬─ .screen  → Writer.videoInput
                                       ├─ .audio   → Writer.systemAudioInput
                                       └─ mic (AVCaptureSession) → Writer.micInput
                  → wait for: duration | Enter or EOF on stdin | SIGINT
                  → Writer.finish() → Report.emit() → JSON to stdout
```

Key pieces and their traps:

- **`SCStreamConfiguration`**: `capturesAudio = true`, `sampleRate = 48000`,
  `channelCount = 2`, `excludesCurrentProcessAudio = true`, `showsCursor`,
  `minimumFrameInterval = CMTime(value: 1, timescale: fps)`, `width`/`height` scaled by
  `--scale` and multiplied by the display's `backingScaleFactor` (otherwise you record at half
  resolution on a Retina display).
- **Dropping empty frames**: ScreenCaptureKit delivers sample buffers with
  `SCStreamFrameInfo.status != .complete` when the screen has not changed. They must be
  filtered out or the video ends up with inflated duration and black frames. A consequence
  worth stating: the output is **variable frame rate**, and `--fps` is a ceiling rather than a
  guarantee. A 5 s capture of a mostly static screen measured 109 frames, not 150. Duration and
  A/V sync are correct because they come from the real presentation timestamps.
- **Colour space**: ScreenCaptureKit hands over frames in the *display's* colour space. The
  built-in XDR panel is Display P3, so leaving this unset produced files holding P3 pixel
  values while the container declared Rec.709 — every player then read those numbers as
  different colours, which looks like a strange cast over the whole picture. Verified against a
  `screencapture` reference: the raw pixel values of the recording were identical to the P3
  screenshot, i.e. no conversion had happened. `colorSpaceName = CGColorSpace.sRGB` makes
  ScreenCaptureKit convert, and the writer states Rec.709 explicitly instead of letting it be
  inferred. Wide-gamut capture (P3 in, P3 tagged) is the alternative; sRGB is chosen because it
  is correct in every player, consistent with `--compatible` elsewhere in the project.

  Worth knowing for the inevitable "the colours look wrong" report: **screen filters are not
  recorded**. Night Shift and True Tone are applied after the framebuffer, so they tint what
  the user sees but never reach the capture. A recording made with Night Shift on will look
  colder than the screen it came from, and that is correct behaviour, not a bug. It produces
  exactly the same complaint as a real colour-space mismatch, so the first question to ask is
  whether a filter is on.
- **`AVAssetWriter`**: `.mov` container, H.264 video (or HEVC with `--codec hevc`), AAC audio.
  The first sample buffer sets `startSessionAtSourceTime`; video and audio share that timeline
  or they drift apart.
- **Nothing captured yet**: a stop arriving before the first video frame leaves a session that
  was never started, and `finishWriting()` then fails with an opaque error. That case cancels
  the write, deletes the empty file and says what happened. The window is a few tens of
  milliseconds — exactly long enough to hit when the stop comes from a script.
- **Clean shutdown**: `SIGINT` **must not** simply kill the process — a `.mov` without a `moov`
  atom is a useless file. A handler marks the inputs with `markAsFinished()` and waits for
  `finishWriting(completionHandler:)` before exiting. That is the difference between "Ctrl-C
  leaves you the video" and "Ctrl-C leaves you garbage".

### 4.3 Audio, specifically

The recorder captures video **and** audio:

- `--audio system` (default): system audio through ScreenCaptureKit. A single AAC track.
  **One TCC permission only** (Screen Recording).
- `--audio mic`: microphone through `AVCaptureSession`, on a separate track. Which device is
  a real choice, unlike system audio, so `cinta devices` enumerates input devices and `--mic`
  selects one by index or `id:UID`. The capture side is forced to mono 16-bit 48 kHz so the
  writer's AAC settings always match the source: the built-in MacBook microphone advertises 3
  channels, and letting that reach the encoder unchanged is a source of silent failures.
- `--audio both`: `cintarec` writes **two audio tracks** into the `.mov` (system and mic) and
  reports them in the JSON. The Python layer then mixes them with ffmpeg (`amix`), which is
  already a dependency. Mixing inside Swift would mean building an `AVAudioEngine` with
  resampling; not worth it when ffmpeg is right there.

  **The mix is not optional in practice.** A two-track file is not a neutral intermediate: every
  player sounds both tracks at once, and the microphone has picked up the speakers a few
  milliseconds late, so the two combine into audible comb filtering. Left unmixed, `--audio
  both` simply sounds broken. So `cinta record` mixes by default and `--keep-tracks` opts out
  for anyone who wants to edit the sources separately. `amix` runs with `normalize=0`, because
  its default divides every input by the number of sources and halves both; the video stream is
  copied, not re-encoded.
- `--audio none`: video only.

### 4.4 Permissions (TCC) — the important surprise

**Screen Recording permission is not granted to `cintarec`, it is granted to your terminal.**
macOS attributes the permission to the "responsible process", which is Terminal.app / iTerm2 /
Ghostty / VS Code. Design consequences:

- On first use you have to open System Settings and enable **your terminal** under Privacy &
  Security → Screen Recording. And **restart the terminal**.
- `cintarec` preflights with `CGPreflightScreenCaptureAccess()`. When permission is missing it
  does not blindly trigger the system dialog: it names the responsible app (read from
  `$TERM_PROGRAM`) so the user does not go looking for `cintarec` in a list that will never
  contain it, and offers to open the pane:
  `open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"`.
- If you switch terminals, you have to do it again. That is inherent to macOS, not to this
  design.
- For the microphone, an `Info.plist` with `NSMicrophoneUsageDescription` is embedded in the
  binary (`-Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist`), because a bare
  executable with no plist cannot request the permission. Attribution still belongs to the
  terminal.

Granted once per terminal and done, but it has to be documented well in the README or first
use will be confusing.

### 4.5 Contract with the Python layer

`cintarec` is a Unix tool: **stdout = JSON, stderr = human logs**, meaningful exit codes.
`core/recorder.py` never parses free-form text.

```jsonc
// cintarec --list
{"displays":[{"index":1,"id":2,"name":"Mi Monitor",
              "width":3440,"height":1440,"scale":1,
              "pixelWidth":3440,"pixelHeight":1440,"isMain":false}],
 "microphones":[{"index":1,"id":"BuiltInMicrophoneDevice",
                 "name":"MacBook Pro Microphone","isDefault":true}],
 "windows":[{"id":512,"app":"Safari","bundleID":"com.apple.Safari",
             "title":"...","width":1440,"height":900}],
 "applications":[{"bundleID":"com.apple.Safari","name":"Safari","pid":403}]}

// cintarec --duration 60 --output out.mov  (on completion)
{"path":"/Users/.../out.mov","durationSeconds":60.02,"fps":30,
 "width":3440,"height":1440,"codec":"h264",
 "display":{"index":1,"id":2,"name":"Mi Monitor","isMain":false, ...},
 "audioTracks":[{"kind":"system","channels":2},
                {"kind":"mic","channels":1,"device":"MacBook Pro Microphone"}],
 "bytes":184029184,"stoppedBy":"duration"}
// stoppedBy is one of: duration | keypress | signal | eof | error
```

Exit codes: `0` ok · `10` no screen permission · `11` no microphone permission ·
`12` target not found (display/window/app) · `13` write failure · `20` invalid arguments.

This contract makes the recorder **testable without recording anything**: the Python tests use
a fake `cintarec` that prints fixture JSON.

---

## 5. Resolving `whisper` and its models

- **The binary**: Homebrew installs the `whisper.cpp` formula, which provides
  `whisper-cli` on the PATH. `external.py` looks for it on the PATH and, as a fallback, in
  `$(brew --prefix)/bin`.
- **The models**: two of them, pinned in the source, with no catalogue and no `--model` flag.
  `ggml-large-v3.bin` for speech and `ggml-silero-v5.1.2.bin` for voice activity detection.
  Choosing a model is a decision the user has no basis to make; cinta takes the most accurate
  one and that is the end of it. When a better model appears, the constant changes, and
  upgrading cinta replaces the file.

  **Why they come with cinta**, given that it is meant to be a thin wrapper: whisper.cpp ships
  no models. Its Homebrew formula installs the binary and a 562 KB test stub, and its caveats
  tell you to go and fetch the real thing from a web page. Two fixed URLs is the whole of it:

  ```
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin
  https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin
  ```

- **Installed with cinta, removed with cinta.** The Homebrew formula downloads both during
  `brew install cinta`, announcing it, into the keg (`libexec/models`), and the wrapper points
  `$CINTA_MODELS_DIR` there. So the first transcription needs nothing, `brew uninstall cinta`
  takes the 3 GB with it, and nothing is left for the user to clean up. How the formula does
  it, and why not with Homebrew resources, is in §6.4.

- **In a source checkout** (`uv run cinta`) there is no formula, so cinta fetches them itself
  on first use, into `~/cinta/models/`, overridable with `$CINTA_MODELS_DIR` or a `models_dir`
  in `config.toml`. Downloads resume: 3 GB that dies at 80% must not start over, so bytes land
  in a `.part` file continued with a `Range` request.

  That directory does not follow `--output-dir` or `$CINTA_OUTPUT_DIR`. Those are
  per-invocation and per-session overrides: writing one recording to an external disk must not
  relocate the models, find the new place empty and download everything again. A `models_dir`
  or `output_dir` in `config.toml` does move them, since a standing preference is a different
  thing from a flag.

- **The profile**: `--vad`, `--temperature 0`, `-mc 0`, `-sns`, `--max-len 192`,
  `--vad-threshold 0.7`, `-l auto`, `-pp`. Tuned rather than default: whisper-cli's own
  defaults hallucinate through silence and repeat themselves on long recordings.

Nothing has to be installed by hand: `brew install cinta` leaves the tool usable, models
included.

`cinta doctor` is out of scope. Its useful parts are distributed where they belong: the
permission check lives in the `cintarec` preflight (§4.4), and a missing model is not something
to check for because the install provides it.

### 5.1 Reading whisper-cli's output

`whisper-cli` writes its transcript to **stdout** and roughly 150 lines of backend and timing
detail to stderr, for a ten-second clip. Inheriting the terminal would put the transcript in the
middle of cinta's own stdout, where only file paths belong, and bury the useful line in noise.

So both streams are read and filtered: transcript segments and the detected language are echoed
to stderr as they arrive, progress is rewritten in place, and everything else is kept only to be
shown if the run fails. `-np` was considered and is not enough — most of the noise comes from
ggml and Metal, below whisper-cli's own printing.

---

## 6. Packaging: uv for development, Homebrew for distribution

### 6.1 What uv does here and what it does not

Two things get confused and must be separated: **uv as the project manager** (development) and
**uv as an installation mechanism** (what runs on the user's machine). uv is excellent at the
former and has no role in the latter, because users install with `brew install` and Homebrew
uses its own Python and its own pip.

**uv is the development and CI tool**, with no conda involved:

```bash
uv python install 3.13      # uv's own CPython, independent of conda and brew
uv sync                     # creates .venv and resolves the development dependencies
uv run pytest
uv build                    # sdist + wheel
uv lock --upgrade
```

`.python-version` pins the interpreter and `uv.lock` locks the development dependencies
(pytest, ruff). Runtime dependencies are still zero, so `uv.lock` only describes the working
environment. `uv run` does not require anything to be activated, which means the miniconda
`python3` that wins on PATH is irrelevant to this project (§6.6). On top of that,
`[tool.uv] python-preference = "only-managed"` in `pyproject.toml` makes it impossible to pick
up a conda or brew interpreter by accident.

### 6.2 The build backend: why `flit_core` and not `uv_build`

The natural choice would be uv's own backend. **It was tried and it breaks Homebrew
installation.** Homebrew builds run without network access, and the install step is a
`pip install` from the source tree:

| Test | Result |
|---|---|
| `uv build --offline` with the `uv_build` backend | ✅ works (uv ships the backend) |
| `pip install --no-index` from source with `uv_build` | ❌ `No matching distribution found for uv_build` |
| `pip install --no-index --no-build-isolation` from source with `flit_core` | ✅ works |
| `uv build` with the `flit_core` backend | ✅ works |

The reason is that the `uv_build` backend only exists *inside* uv; pip does not have it and
cannot fetch it without network access. We could add `depends_on "uv" => :build` and build the
wheel in the formula, but that drags in a 40 MB build dependency to save a six-line block.

**The backend is `flit_core`**: no transitive dependencies, which means a single `resource` in
the formula. `hatchling` would work too, at the cost of five `resource` blocks instead of one;
the only option ruled out on technical grounds is `uv_build`.

### 6.3 The other decision that simplifies everything

Homebrew installs Python packages with `virtualenv_install_with_resources`, which requires
**every transitive Python dependency** to be declared as a `resource` block in the formula.
With yt-dlp as a library that means ~10 resources and a formula bump every time yt-dlp
releases (which is almost weekly — the current one is 2026.8.19).

**Chosen design: `cinta` has no Python dependencies at all.** yt-dlp is invoked as a subprocess
and already exists as its own Homebrew formula (`depends_on "yt-dlp"`). The CLI parser is
stdlib `argparse`, not Typer/Click.

What this buys:

- A formula without a single `resource` block. Nothing to touch when yt-dlp updates.
- `brew upgrade yt-dlp` fixes YouTube breakage **without touching this package**.
- Trivial installation and uninstallation.

What it costs: yt-dlp metadata arrives as JSON instead of as a Python object (one `json.loads`,
trivial), and zsh completions have to be written by hand instead of generated by Typer (~40
lines of `compdef`, done once).

### 6.4 The formula

The formula is `packaging/homebrew/cinta.rb`. That copy is the source of truth; the tap
(`github.com/alexdlp/homebrew-tap`) receives it with `url` and `sha256` filled in for each
release. It passes `brew audit --strict --new`, `brew install --build-from-source` and
`brew test`.

What it does and why:

- **Dependencies**: `ffmpeg`, `whisper.cpp`, `yt-dlp`, `python@3.14` (Homebrew's current
  Python, so CI tests it too) and macOS 13. No `depends_on xcode`: the Command Line Tools,
  which Homebrew already requires, include Swift, and demanding a full Xcode would lock out
  anyone who does not have it.
- **One resource**, `flit-core`, the build backend (§6.2).
- **Not `virtualenv_install_with_resources`**: that links `bin/cinta` straight to the
  virtualenv, and `bin/cinta` has to be a wrapper that sets `CINTA_RECORDER`. So the formula
  creates the virtualenv, installs into it, and writes the wrapper itself.
- **`cintarec` goes into `libexec/`**, not `bin/`: it is an implementation detail, not a public
  tool. `swift build --disable-sandbox`, because SwiftPM's sandbox cannot nest inside
  Homebrew's.
- **The test** needs no permissions, so it runs anywhere: both versions match the formula, the
  help lists the commands, and `cintarec --fps 0` exits with 20, which proves the binary starts
  and parses before it would ask macOS for anything.
- **The models are downloaded in `install`**, with `curl`, into `libexec/models`, each announced
  with its size and checked against its SHA-256. Not as `resource` blocks: Homebrew keeps a
  copy of every resource in its download cache, which would be a second 3 GB outliving the
  install. Not in `post_install` either: it is deprecated in favour of `post_install_steps`,
  which is a fixed set of file operations and cannot download.
- **On upgrade the models are not downloaded again.** The installed version is still in the
  Cellar while the new one installs, so the formula hard-links its copy: instant, no extra
  space, and the file survives when Homebrew removes the old keg. Only a changed model (a new
  SHA-256) is fetched. A formula change with no new release is a `revision` bump.
- **No bottles.** A bottle built from this formula would carry the models, and 3 GB is over
  GitHub's 2 GB limit per release file. Building from source costs about a minute of
  `swift build`, small beside the model download the install does anyway.
- **The caveats** say the one thing a user cannot guess: the screen recording permission
  belongs to the terminal.

### 6.5 Installation and uninstallation

```bash
brew tap alexdlp/tap        # once
brew trust alexdlp/tap      # once: Homebrew loads no third-party formula until trusted
brew install cinta
brew upgrade cinta
brew uninstall cinta
```

`brew install cinta` with no tap at all needs the formula in homebrew-core, which accepts
projects once they are notable (roughly 75 stars or 30 forks). The tap comes first; the
formula moves to homebrew-core unchanged when that happens, and the `brew tap` line goes.

`brew uninstall cinta` removes everything cinta installed, the models included. What stays is
what the user made: recordings, downloads and transcripts in `~/cinta/`, and a
`~/.config/cinta/config.toml` if they wrote one. Those are documents, and no uninstaller
deletes documents.

### 6.6 Taking miniconda out of the equation

A miniconda installation puts `/opt/homebrew/Caskroom/miniconda/base/bin` **before**
`/opt/homebrew/bin` on PATH, so `python3` and `yt-dlp` resolve to conda's copies. This affects
the design in two separate places:

**In development the problem disappears on its own:** uv uses its own CPython
(`uv python install 3.13`) and `uv run` does not consult PATH to choose an interpreter. There is
no need to uninstall conda or edit PATH to work on the project. `uv` itself lives in
`~/.local/bin` (standalone install, not from conda), so there is no chicken-and-egg problem
either.

**At runtime there is a real design decision to make.** Once the formula is installed there
will be two `yt-dlp` binaries and conda's will win by PATH order — and with it a version nobody
controls and Homebrew does not update. That is why `external.py` **does not look tools up on
PATH blindly**. Resolution order for `yt-dlp`, `ffmpeg` and `whisper-cli`:

1. An explicit environment variable (`$CINTA_YTDLP`, `$CINTA_FFMPEG`, …)
2. `config.toml`
3. The sibling directory of `cinta` itself (inside the Homebrew prefix)
4. `$(brew --prefix)/bin`
5. PATH, as a last resort

That way `cinta` always uses the tools Homebrew installed as its own dependencies, whether conda
comes first or last. And it stays overridable if some day you want to point at another binary.

---

## 7. Tests

Target: ~80% on `src/cinta/core/`. The rule is that **everything touching the outside world
lives in `external.py`** and is replaced by a double in tests.

**Unit** (fast, no network, no subprocesses):

- yt-dlp format selectors: `--compatible` produces the H.264/AAC chain, and it still ends in
  the generic fallback.
- argv construction, with snapshots: ffmpeg to WAV, `whisper-cli`, `cintarec`. Catches flag
  regressions without executing anything.
- Reading back the paths yt-dlp reports through `--print-to-file`, for a single video and for
  a playlist.
- Parsing the `cintarec` JSON and mapping its exit codes to errors with useful messages.
- Model handling: the two files are pinned, and one already on disk is never downloaded again.
- Output path derivation and filename sanitization.

**Integration** (`pytest -m integration`, outside the fast loop): real ffmpeg, whisper-cli and
yt-dlp, and the same large-v3 and Silero models a user gets. A smaller model would be testing
something cinta never runs.

- The media is generated, not committed: `say -v Samantha` speaks a known sentence, and the
  tests check those words come back. A tone would not work, since voice-activity detection
  correctly finds no speech in it. The voice is named because the default follows the system
  language, and a Spanish voice reading English is transcribed as something else.
- `cinta transcribe` over an audio file and a video: both transcripts hold the sentence, and
  the `.srt` has timestamps.
- `cinta transcribe` with a corrupt file first: it fails alone, the good file is still
  transcribed, and the exit code is nonzero.
- `cinta download` against a **`file://` URL**, to run the full yt-dlp pipeline without
  depending on YouTube or the network: video by default, MP3 with `--audio`, and
  `--transcribe` leaving the media and its transcript in one folder.

**Recording** (`pytest -m recording`, by hand): three seconds of real screen, checked with
`ffprobe` for duration, H.264 with even dimensions, and the right number of audio tracks. It
cannot run in CI, since runners have no display and no screen recording permission, so it is
run locally after touching `cintarec` and before a release.

**Swift** (swift-testing, which ships with the Command Line Tools; XCTest needs a full Xcode):

- Argument parsing and validation (`--fps 0`, `--scale 1.5`, incompatible flags, missing
  values). The parser throws instead of exiting, so every rejection is testable.
- Building `SCStreamConfiguration` from the options: pixels rather than points, even
  dimensions, system audio only when asked for.
- The JSON shape of `--list` and of the report, key by key, since Python reads them by name.

**Across the boundary** (`tests/unit/test_contract.py`, in Python because it reads both sides):
every exit code `cintarec` defines has an explanation in `errors.py`, and the version is the
same in `pyproject.toml`, `__init__.py` and `main.swift`.

**CI** (GitHub Actions, `macos-15` runner):

| Job | Contents |
|---|---|
| `lint` | `uv run ruff check` and `ruff format --check` over `src/` and `tests/` |
| `test` | `uv run pytest` unit tests on Python 3.11 to 3.14 |
| `integration` | `pytest -m integration`, tools from Homebrew, the models cached between runs |
| `swift` | `swift test` + `swift build -c release` + `cintarec --version` |
| `brew` | the formula pointed at this commit: `brew audit --strict`, `brew install --build-from-source`, `brew test`, then `brew uninstall` and a check that no model is left |

---

## 8. Open decisions and risks

1. **yt-dlp as a subprocess rather than a library.** Hugely simplifies packaging (§6.3).
   `core/downloader.py` is the only module that knows how yt-dlp is invoked, so switching to
   the library would stay contained there.
2. **Compiling Swift on every install** takes ~1 min and requires the Xcode Command Line Tools,
   which Homebrew requires anyway. Bottles would remove it but cannot carry the models (§6.4),
   so every install builds from source.
3. **macOS 13 minimum.** Leaves Monterey out. In exchange, system audio without drivers. Given
   that development happens on macOS 26, the real cost is zero.
4. **The output `.mov`** uses H.264 for QuickTime compatibility (consistent with the
   `--compatible` flag that already exists for downloads). HEVC sits behind `--codec hevc`.
5. **Package name.** `cinta` everywhere: Homebrew formula, Python module, command and
   repository. Verified free on the local PATH, in homebrew-core and on PyPI.
6. **Narration (`--audio both`) is usable but not good, and that is physics.** Recording the
   microphone while sound plays through speakers means the microphone hears the speakers a few
   milliseconds late. Two tracks sound hollow, a mix sounds like an echo; both are the same
   defect. Headphones remove it entirely, and no amount of processing on our side matches that.
   If narration ever becomes a real use case, the useful work is not echo cancellation but
   input control: per-source levels, a noise gate, and a meter to check the microphone before
   committing to a long take. Until then, the honest documentation is "use headphones", and the
   default stays system audio only.
7. **`uv_build` is ruled out as a backend** because of the offline-install incompatibility with
   Homebrew (§6.2). If Homebrew ever adopts uv for installing Python packages, the decision is
   worth revisiting: it is a two-line change in `pyproject.toml`.
