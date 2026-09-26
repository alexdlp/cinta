# Design: `cinta` — a macOS command-line suite for recording, downloading and transcribing media

> Design document. Status: the repository is initialized (uv project, package skeleton, test
> layout). None of the commands are implemented yet.
> Decisions made: distribution through a **Homebrew tap**, a single **`cinta` CLI with
> subcommands**, a Swift recorder capturing **video + audio**, **uv** as the project manager,
> and a scope of **download + transcribe + batch + record + models**.

## What `cinta` does

`cinta` captures audio and video on a Mac and turns it into text. There are two ways in and
one way out:

| | Command | What it gets you |
|---|---|---|
| **In, from the internet** | `cinta download` | Audio or video from any site `yt-dlp` supports |
| **In, from your own screen** | `cinta record` | A screen recording with system audio and/or microphone |
| **Out, as text** | `cinta transcribe`, `cinta batch` | A transcript of any media, local or remote |

Supporting cast: `cinta models` manages the Whisper models the transcription runs on.

Two properties worth stating up front, because they drive most of the design:

- **Transcription is local.** Audio never leaves the machine; `whisper.cpp` runs on-device.
- **There is no GUI and no daemon.** Every subcommand is a one-shot Unix tool: stdout carries
  data, stderr carries logs, the exit code means something.

---

## 1. Starting point and what fails today

| Script | What it does | Why it resists packaging |
|---|---|---|
| `media_download` | yt-dlp as a Python library | A Python dependency that changes every week |
| `media_transcribe` | Loads `media_download` with `SourceFileLoader` | Coupled by file path; not a real import |
| `whisper` | Bash wrapper around `whispercpp` | Hardcoded `~/whisper.cpp/models/*.bin` paths |
| `whisper_here` | ffmpeg + whisper loop over the cwd | Only works in the cwd, no per-file error handling |
| `whispercpp` | **Symlink to `/Users/alexdelapuente/whisper.cpp/build/bin/whisper-cli`** | Impossible to distribute |
| `record_screen` | Drives OBS over WebSocket | OBS opened by hand, WebSocket enabled by hand, input name hardcoded in Spanish, **password in cleartext in the source** |

Three real blockers to "anyone can use this":

1. **The `whispercpp` symlink and the `~/whisper.cpp/` paths** are specific to one machine.
2. **OBS** requires manual setup and cannot be automated reliably.
3. **There was no project**: no git, no tests, no package metadata, no license.

Note: the repository had no git history when this was written, which is a piece of luck — the
OBS WebSocket password (`record_screen:20`) disappears with the file and never enters the
history. The old scripts were moved out of the repository *before* the first commit, not after.

Note 2: the old README documented `udemy_scan`, but **that script did not exist in the
directory**. It is out of scope and was dropped along with the old README.

---

## 2. Design principles

1. **One compiled binary.** The only thing that gets compiled is the Swift recorder. Everything
   else is pure Python.
2. **Zero Python runtime dependencies.** See §7: this turns the Homebrew formula into something
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

## 3. Repository layout

```
cinta/
├── pyproject.toml              # no [build-system] until packaging (§7.2)
├── README.md                   # user-facing
├── DESIGN.md                   # this document
├── CHANGELOG.md
├── LICENSE                     # MIT
├── Makefile                    # make build-swift / test / fmt
├── src/cinta/
│   ├── __init__.py             # __version__
│   ├── cli.py                  # root parser + subcommand dispatch
│   ├── config.py               # XDG paths, config.toml, environment variables
│   ├── duration.py             # '30s' / '5m' / '1h30m' -> seconds
│   ├── errors.py               # CintaError -> exit codes
│   ├── external.py             # THE ONLY place that spawns subprocesses
│   ├── ui.py                   # progress, colors, --json/--quiet modes
│   ├── commands/
│   │   ├── devices.py
│   │   ├── download.py
│   │   ├── transcribe.py
│   │   ├── batch.py
│   │   ├── record.py
│   │   └── models.py
│   └── core/
│       ├── downloader.py       # yt-dlp argv construction + -J parsing
│       ├── media.py            # ffmpeg: to 16k mono WAV, track mixing
│       ├── whisper.py          # whisper-cli argv + model resolution
│       ├── recorder.py         # client for the Swift binary (JSON contract)
│       ├── models.py           # catalog, download and verification of models
│       └── transcript.py       # metadata header of the .txt
├── swift/cintarec/
│   ├── Package.swift           # swift-tools-version:5.9, .macOS(.v13)
│   ├── Info.plist              # NSMicrophoneUsageDescription (embedded)
│   └── Sources/cintarec/
│       ├── main.swift          # hand-rolled argument parsing (no SPM deps)
│       ├── Shareable.swift     # SCShareableContent -> --list as JSON
│       ├── Recorder.swift      # SCStream + delegates
│       ├── Writer.swift        # AVAssetWriter (video + audio)
│       ├── Permissions.swift   # TCC preflight
│       └── Report.swift        # output JSON
├── tests/
│   ├── unit/                   # no network, no real subprocesses
│   ├── integration/            # marked, use ffmpeg and the tiny model
│   └── fixtures/               # 3s wav, yt-dlp JSON, cintarec JSON
├── uv.lock                     # lock file for the development dependencies
├── .python-version             # CPython managed by uv, not by conda
├── .github/workflows/ci.yml
└── packaging/homebrew/cinta.rb   # copied into the tap
```

Removed from the repository: `whispercpp` (symlink), `whisper`, `whisper_here`,
`media_download`, `media_transcribe`, `record_screen`. They are kept outside the repository as
a reference while their logic is ported, and deleted once it is.

---

## 4. The `cinta` CLI

A single entry point. `pyproject.toml` declares `cinta = "cinta.cli:main"`.

```
cinta [--json] [--quiet] [-v] <subcommand> ...

  devices                  List screens and microphones
  download    URL          Download audio or video
  transcribe  [PATHS...]   Transcribe media into text
  record      [DURATION]   Record the screen
  record      [DURATION]   Record the screen
  models      <action>     Manage Whisper models
  version
```

**Durations always carry a unit**: `30s`, `5m`, `1h30m`. A bare number is refused rather than
interpreted. The two plausible readings of `15` are sixty times apart, and a duration is only
ever typed when the recording is about to be left unattended, so the error names both spellings
instead of guessing. The unit is parsed once in `duration.py` and every command that takes a
length of time uses it.

### 4.0 Where output goes and what it is called

**One destination directory for everything the tool produces: `~/cinta/`, flat.**

The reason it is not split by file type is that a single run produces several files.
`cinta transcribe URL` writes the media, the `.txt` and the `.srt`; `cinta record` may later
write a `.mov` plus a sidecar. Sending video to `~/Movies`, audio to `~/Music` and text to
`~/Documents` would tear one job's results across three folders. They share a filename stem
instead, which keeps them adjacent in any sorted listing. `~/Desktop` is rejected for the
obvious reason: screen recordings run about 15 MB per minute and the desktop is visible.

Resolution order for the destination:

1. `--output FILE` — an exact path. Only for commands that produce exactly one file.
2. `--output-dir DIR`
3. `$CINTA_OUTPUT_DIR`
4. `output_dir` in `~/.config/cinta/config.toml`
5. `~/cinta/`, created on first use.

Naming contract:

| Command | Produces | Name |
|---|---|---|
| `download --type audio` | `.mp3` | `<title>.mp3`, the title from yt-dlp, sanitized |
| `download --type video` | `.mp4` / `.mkv` | `<title>.<ext>` |
| `record` | `.mov` | `<YYYY-MM-DD>-<HHMMSS>-<display>.mov` |
| `transcribe` | media + `.txt` + `.srt` | the media's stem, reused for the sidecars |
| `batch` | `.txt` + `.srt` per input | the input's stem |

Rules that apply to all of them:

- **Date first** in generated names, so `ls` sorts chronologically.
- **Sanitization**: no `/`, no leading dots, whitespace collapsed, trailing dots and spaces
  trimmed (they break on other filesystems).
- **Never overwrite silently.** An existing destination is an error (exit code 13) unless
  `--force` is given.
- One job's outputs **share a stem**. That is the whole organizing principle; there are no
  per-type subdirectories, and no per-job subdirectory either — a folder holding a single
  `.mp3` is worse than a flat listing.

Open question: `batch` takes local files as input, and today's `whisper_here` writes next to
them (`./transcripciones`). Writing those transcripts to `~/cinta/` instead means transcribing
`~/lectures/*.mp4` scatters the results away from the videos. Leaning towards: `batch` defaults
to writing beside each input file, because there the user already chose a location. To be
confirmed when `batch` is implemented.

### 4.1 `cinta download`

```
cinta download URL [--type audio|video] [--output-dir DIR] [--playlist]
                [--keep-temp] [--compatible] [--format SELECTOR]
```

The same flags as today plus one new one (`--format`, an escape hatch to pass a raw yt-dlp
selector). Default behaviour is unchanged: `audio` as MP3 in `~/Desktop`.

**One important internal change.** Today `final_paths_from_info()` *infers* the final path by
reimplementing yt-dlp's post-processing logic — and gets it wrong the moment yt-dlp changes
anything. It is replaced by asking yt-dlp directly:

```
yt-dlp --print after_move:filepath --no-simulate ...
```

That returns the real path of each file after post-processing, one per line. Less code, no
guessing. Metadata (title, channel, date, duration) comes from `--print-json` in the same pass,
so there is no second network request.

### 4.2 `cinta transcribe`

```
cinta transcribe URL [--type audio|video] [--output-dir DIR] [--compatible]
                  [--keep] [--keep-wav] [--lang es|auto] [--model NAME]
```

Pipeline: `download` → (if needed) `ffmpeg` to 16 kHz mono WAV → `whisper-cli` → prepend the
metadata header to the `.txt`. Same as today, except:

- `download` is **imported** instead of being loaded with `SourceFileLoader`.
- `--lang` and `--model` stop being hardcoded in the bash wrapper.
- If yt-dlp returns several files, they are transcribed in sequence instead of `sys.exit(1)`.

### 4.3 `cinta transcribe` absorbs what was going to be `cinta batch`

The plan had two commands split by where the input came from: `transcribe URL` and
`batch PATHS`. That split is an implementation detail leaking into the interface — from the
outside both are "turn this into text", and nobody remembers which verb takes which kind of
argument. One command takes any number of arguments; a URL is just another kind of argument
once `download` exists. Multiple files is not a separate mode, it is several arguments.

### 4.3b The old `cinta batch` design, kept for its error handling

```
cinta batch [PATHS...] [--ext mp4] [--output-dir DIR] [--jobs N] [--skip-existing]
```

Successor to `whisper_here`. With no arguments it behaves exactly as today (`*.mp4` from the
cwd into `./transcripciones`), but it accepts explicit paths and globs, `--skip-existing` to
resume an interrupted batch, and one failing file no longer aborts the rest: it is recorded and
the run continues. The final summary lists successes and failures, and the exit code is nonzero
if there was any failure.

### 4.4 `cinta record`

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
- It fully replaces `record_screen`: OBS, `obsws-python`, `tqdm`, port 4455 and the hardcoded
  password all go away.

### 4.5 `cinta models`

```
cinta models list                    # catalog + which ones you have and how big they are
cinta models download NAME           # download with a progress bar and resumption
cinta models path [NAME]             # print the resolved path (for scripts)
cinta models remove NAME
cinta models verify [NAME]           # check SHA-256 against the catalog
```

The catalog ships **embedded in the package** as a TOML file: name, Hugging Face URL, size and
expected SHA-256. The network is never used to "discover" models, only to fetch them.

Concrete decisions:

- **Resumable downloads.** `large-v3` is ~3 GB; a download that dies at 80% and restarts from
  zero is unacceptable. HTTP `Range` over a `.part` file, renamed on completion. Implemented
  with stdlib `urllib` — no need for `requests`, which keeps the zero-dependency rule.
- **Mandatory SHA-256 verification** before renaming the `.part`. A truncated model makes
  `whisper-cli` fail with an incomprehensible error; better to catch it at download time.
- **The VAD model is in the catalog** (`silero-v5.1.2`), because the default transcription
  profile uses it (§6) and today it is assumed to exist under `~/whisper.cpp`.
- **How it ties into the rest of the CLI:** when `cinta transcribe` or `cinta batch` cannot find
  the model, the error is not a stack trace but `missing model 'large-v3'; run: cinta models
  download large-v3`. That is the reason this subcommand is in scope at all.
- `cinta models list --json` so it can be scripted.

---

## 5. The native recorder: `cintarec` (Swift + ScreenCaptureKit)

### 5.1 Why ScreenCaptureKit and nothing else

| Option | Verdict |
|---|---|
| **ScreenCaptureKit** | ✅ System audio **without drivers** (no BlackHole). Capture by display, window or app. Hardware encoding. Requires macOS 13. **Chosen.** |
| `screencapture -V` | Built into the system, but no system audio and no fine-grained control. Useful only as a fallback. |
| `ffmpeg -f avfoundation` | Needs a loopback device (BlackHole) for system audio. Reintroduces manual installation: exactly the OBS problem. |

The development machine runs macOS 26.6.2 and Swift 6.4, so this is comfortable. The macOS 13
floor is there for other users, not for it.

### 5.2 Architecture of the binary

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

### 5.3 Audio, specifically

The recorder captures video **and** audio:

- `--audio system` (default): system audio through ScreenCaptureKit. A single AAC track.
  **One TCC permission only** (Screen Recording). It is what OBS did with the "macOS Screen
  Capture" input, without OBS.
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

### 5.4 Permissions (TCC) — the important surprise

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

**This counts in favour of the design over OBS**, not against it: granted once per terminal and
done. But it has to be documented well in the README or first use will be confusing.

### 5.5 Contract with the Python layer

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

## 6. Resolving `whisper` and its models

The `whispercpp` symlink and the `~/whisper.cpp/` paths are gone.

- **The binary**: Homebrew installs the `whisper.cpp` formula (v1.9.4 today), which provides
  `whisper-cli` on the PATH. `external.py` looks for it on the PATH and, as a fallback, in
  `$(brew --prefix)/bin`.
- **The models**: two of them, pinned in the source, with no catalogue and no `--model` flag.
  `ggml-large-v3.bin` for speech and `ggml-silero-v5.1.2.bin` for voice activity detection.
  Choosing a model is a decision the user has no basis to make; cinta takes the most accurate
  one and that is the end of it. When a better model appears, the constant changes, and
  upgrading cinta replaces the file.

  **Why cinta downloads them at all**, given that it is meant to be a thin wrapper: whisper.cpp
  ships no models. Its Homebrew formula installs the binary and a 562 KB test stub, and its
  caveats tell you to go and fetch the real thing from a web page. The script that makes this
  painless (`models/download-ggml-model.sh`) lives in the source repository, which Homebrew does
  not install — which is why anyone who built from source has models without remembering how.
  Two fixed URLs is the whole of it:

  ```
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin
  https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v5.1.2.bin
  ```

  Downloads resume: 3 GB that dies at 80% must not start over, so bytes land in a `.part` file
  continued with a `Range` request.

- **Where they live**: `~/cinta/models/`, overridable with `$CINTA_MODELS_DIR`.

  whisper.cpp has no opinion — its `-m` default is `models/ggml-base.en.bin`, a path relative to
  the working directory, left over from running inside the source tree. So the location is
  cinta's to choose. It goes under the output directory because cinta owns these files' whole
  life: it downloads them, replaces them on upgrade and removes them on request. One directory
  for everything, so `rm -rf ~/cinta` leaves nothing behind.

  Rejected: `$(brew --prefix)/share/whisper.cpp/`, because that path contains the version
  number. `brew upgrade whisper.cpp` would delete 3 GB and give nothing back — the formula has
  no models to replace them with.

- The options currently hardcoded in the bash wrapper (`--vad`, `--temperature 0`, `-mc 0`,
  `-sns`, `--max-len 192`, `--vad-threshold 0.7`, `-l auto`, `-pp`) become the **default
  profile** in `config.toml`, overridable by flags. Nothing is lost, control is gained.

Models are managed by `cinta models` (§4.5), which writes to level 4 of that list. The install
path requires no downloads: `brew install` leaves the tool usable, and
`cinta models download large-v3` leaves it complete.

`cinta doctor` is out of scope. Its useful parts are distributed where they belong: the
permission check lives in the `cintarec` preflight (§5.4), and a missing model is not something
to check for because cinta fetches it.

### 6.1 Reading whisper-cli's output

`whisper-cli` writes its transcript to **stdout** and roughly 150 lines of backend and timing
detail to stderr, for a ten-second clip. Inheriting the terminal would put the transcript in the
middle of cinta's own stdout, where only file paths belong, and bury the useful line in noise.

So both streams are read and filtered: transcript segments and the detected language are echoed
to stderr as they arrive, progress is rewritten in place, and everything else is kept only to be
shown if the run fails. `-np` was considered and is not enough — most of the noise comes from
ggml and Metal, below whisper-cli's own printing.

---

## 7. Packaging: uv for development, Homebrew for distribution

### 7.1 What uv does here and what it does not

Two things get confused and must be separated: **uv as the project manager** (development) and
**uv as an installation mechanism** (what runs on the user's machine). uv is excellent at the
former and has no role in the latter, because users install with `brew install` and Homebrew
uses its own Python and its own pip.

**uv is the development and CI tool.** It replaces conda entirely:

```bash
uv python install 3.13      # uv's own CPython, independent of conda and brew
uv sync                     # creates .venv and resolves the development dependencies
uv run pytest
uv build                    # sdist + wheel
uv lock --upgrade
```

`[tool.uv] python-preference = "only-managed"` in `pyproject.toml` makes it impossible to pick
up a conda or brew interpreter by accident.

`.python-version` pins the interpreter and `uv.lock` locks the development dependencies
(pytest, ruff). Runtime dependencies are still zero, so `uv.lock` only describes the working
environment. `uv run` does not require anything to be activated, which means the miniconda
`python3` that currently wins on PATH is irrelevant to this project (§7.6). On top of that,
`[tool.uv] python-preference = "only-managed"` in `pyproject.toml` makes it impossible to pick
up a conda or brew interpreter by accident.

### 7.2 The build backend: why `flit_core` and not `uv_build`

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

**This was originally deferred, and the deferral was wrong.** The plan was to ship no
`[build-system]` at all until packaging day, on the grounds that `uv sync` works without one —
which is true, uv treats such a project as "virtual" and does not build it. What that misses is
that a virtual project is never *installed* into the venv, so with a `src/` layout there is no
`cinta` executable and no importable `cinta` module. In practice that meant:

- `uv run cinta` — the obvious thing to type — failed with "Failed to spawn: `cinta`".
- `uv run python -m cinta` failed too, needing a `PYTHONPATH=src` prefix wrapped in a Makefile.
- Running the CLI from anywhere else needed a 140-character shell alias.
- `pytest` needed `pythonpath = ["src"]` to see the package at all.

The fix is three lines of `pyproject.toml` and it deletes all four workarounds. The lesson is
narrow and worth keeping: deferring the build backend is only free for a library nobody runs
from the command line. For a project whose whole point is a command, the backend is what makes
the command exist, so it belongs in from the start.

### 7.3 The other decision that simplifies everything

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

### 7.4 Formula skeleton

```ruby
class Cinta < Formula
  include Language::Python::Virtualenv

  desc "Record, download and transcribe audio and video from the command line"
  homepage "https://github.com/alexdlp/cinta"
  url "https://github.com/alexdlp/cinta/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "..."
  license "MIT"

  depends_on "python@3.13"
  depends_on "ffmpeg"
  depends_on "yt-dlp"
  depends_on "whisper.cpp"
  depends_on macos: :ventura          # ScreenCaptureKit + system audio
  depends_on xcode: ["15.0", :build]  # to compile cintarec

  # The project's only resource: the build backend. No transitive dependencies.
  resource "flit_core" do
    url "https://files.pythonhosted.org/packages/.../flit_core-4.1.0.tar.gz"
    sha256 "..."
  end

  def install
    virtualenv_install_with_resources   # runtime: zero deps; build: flit_core only

    system "swift", "build", "-c", "release", "--disable-sandbox",
           "--package-path", "swift/cintarec"
    libexec.install "swift/cintarec/.build/release/cintarec"

    (bin/"cinta").write_env_script libexec/"bin/cinta",
      CINTA_RECORDER: libexec/"cintarec"
  end

  def caveats
    <<~EOS
      Screen recording: macOS grants the permission to your TERMINAL, not to cinta.
        Settings -> Privacy & Security -> Screen Recording -> enable your terminal
        and restart it.

      Whisper models are not bundled (~3 GB). To transcribe:
        cinta models download large-v3
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/cinta version")
    assert_match "usage", shell_output("#{bin}/cinta --help")
    assert_match "large-v3", shell_output("#{bin}/cinta models list")  # catalog, no network
    system libexec/"cintarec", "--version"   # needs no TCC
  end
end
```

`cintarec` goes into `libexec/` rather than `bin/`: it is an implementation detail, not a public
tool. `cinta` locates it through the `CINTA_RECORDER` variable.

### 7.5 Installation and uninstallation

```bash
brew tap alexdlp/tap
brew install cinta          # or --build-from-source until there is a bottle
brew uninstall cinta
brew untap alexdlp/tap
```

Homebrew **never** deletes user data. After uninstalling these remain, and it has to be
documented:

- `~/.config/cinta/` (configuration)
- `~/Library/Application Support/cinta/models/` (models, the gigabytes)

The README will include the `rm -rf` line for full removal. `cinta models remove --all` handles
the heavy part (the gigabytes of models) safely before uninstalling.

### 7.6 Taking miniconda out of the equation

Verified on the development machine: `/opt/homebrew/Caskroom/miniconda/base/bin` comes **before**
`/opt/homebrew/bin` on PATH, so today `python3` and `yt-dlp` resolve to conda's. This affects
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

## 8. Tests

Target: ~80% on `src/cinta/core/`. The rule is that **everything touching the outside world
lives in `external.py`** and is replaced by a double in tests.

**Unit** (fast, no network, no subprocesses):

- yt-dlp format selectors: `--type video --compatible` produces the H.264/AAC string.
- argv construction, with snapshots: ffmpeg to WAV, `whisper-cli`, `cintarec`. Catches flag
  regressions without executing anything.
- Parsing the JSON from `yt-dlp --print-json` → metadata header (including the awkward cases
  the current code already handles: malformed `upload_date`, `duration` of `None`).
- Parsing the `cintarec` JSON and mapping its exit codes to errors with useful messages.
- Model resolution: the 5 precedence levels from §6.
- Output path derivation and filename sanitization.

**Integration** (marked `@pytest.mark.integration`, outside the fast loop):

- A 3 s WAV generated with `ffmpeg -f lavfi -i sine` → `whisper-cli` with the **tiny** model
  (75 MB, cached in CI) → assert that non-empty `.txt` and `.srt` come out.
- `cinta download` against a local **`file://` URL** (yt-dlp supports them) to exercise the full
  pipeline without depending on YouTube or the network.
- `cinta batch` over a temporary directory with 3 files, one of them corrupt: verifies the other
  two are processed and the exit code is nonzero.

**Swift** (XCTest):

- Argument parsing and validation (`--fps 0`, nonexistent `--display`, incompatible flags).
- Building `SCStreamConfiguration` from the options.
- Serializing `Report` to JSON.
- Real recording **is not testable in CI**: runners have no TCC permissions and no attached
  display. It is covered by a smoke run that records 3 s locally and validates the `.mov` with
  `ffprobe` (duration, codec, track count).

**CI** (GitHub Actions, `macos-15` runner):

| Job | Contents |
|---|---|
| `lint` | `uv run ruff check` and `ruff format --check` over `src/` and `tests/` |
| `test` | `uv run pytest` unit tests on Python 3.11/3.12/3.13 (`uv python install`) |
| `integration` | `pytest -m integration` with ffmpeg and the tiny model cached |
| `swift` | `swift build -c release` + `swift test` |
| `brew` | `brew install --build-from-source` from the tap + `brew test` + `brew audit --strict` |

Static type checking is deliberately absent. `mypy --strict` over code whose job is to move
`dict[str, Any]` from a `json.loads` into a subprocess argument list costs more annotation than
it catches, on a project with one maintainer and no public API. It can be added later if the
JSON boundaries start causing real bugs.

---

## 9. Open decisions and risks

1. **yt-dlp as a subprocess rather than a library.** Hugely simplifies packaging (§7.3), but it
   is a real change from the current code. `core/downloader.py` sits behind an interface in case
   it ever has to be reverted.
2. **Compiling Swift on every install** takes ~1 min and requires the Xcode Command Line Tools.
   Solved by publishing bottles from CI; not a blocker for the formula to work.
3. **The model catalog carries fixed SHA-256 hashes.** If Hugging Face republishes a `.bin`,
   verification will fail and the catalog has to be updated. That is the price of detecting
   corrupt downloads, and a loud failure beats a silent one.
4. **macOS 13 minimum.** Leaves Monterey out. In exchange, system audio without drivers. Given
   that development happens on macOS 26, the real cost is zero.
5. **The output `.mov`** uses H.264 for QuickTime compatibility (consistent with the
   `--compatible` flag that already exists for downloads). HEVC sits behind `--codec hevc`.
6. **Package name.** `cinta` everywhere: Homebrew formula, Python module, command and
   repository. Verified free on the local PATH, in homebrew-core and on PyPI.
7. **Narration (`--audio both`) is usable but not good, and that is physics.** Recording the
   microphone while sound plays through speakers means the microphone hears the speakers a few
   milliseconds late. Two tracks sound hollow, a mix sounds like an echo; both are the same
   defect. Headphones remove it entirely, and no amount of processing on our side matches that.
   If narration ever becomes a real use case, the useful work is not echo cancellation but
   input control: per-source levels, a noise gate, and a meter to check the microphone before
   committing to a long take. Until then, the honest documentation is "use headphones", and the
   default stays system audio only.
8. **`uv_build` is ruled out as a backend** because of the offline-install incompatibility with
   Homebrew (§7.2). If Homebrew ever adopts uv for installing Python packages, the decision is
   worth revisiting: it is a two-line change in `pyproject.toml`.
