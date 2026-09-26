"""The whisper-cli command line. Snapshot-style: these catch a flag going
missing without running a transcription."""

from pathlib import Path

import pytest

from cinta.core import media, whisper


@pytest.fixture
def arguments():
    return whisper.transcribe_arguments(
        audio=Path("/tmp/clip.wav"),
        output_stem=Path("/out/clip"),
        model=Path("/models/large.bin"),
        vad_model=Path("/models/vad.bin"),
    )


def value_after(arguments, flag):
    return arguments[arguments.index(flag) + 1]


def test_voice_activity_detection_is_on_with_its_model(arguments):
    """Without VAD, Whisper invents text through silence: it repeats the last
    line or produces sentences nobody said. The model has to be passed too --
    --vad alone is not enough, whisper-cli's default vad-model is empty."""
    assert "--vad" in arguments
    assert value_after(arguments, "--vad-model") == "/models/vad.bin"
    assert value_after(arguments, "--vad-threshold") == "0.7"


def test_decoding_is_deterministic_and_without_carried_context(arguments):
    """Temperature above zero makes Whisper sample, which invents more than it
    fixes on lecture audio. Carried context is what makes it repeat itself for
    minutes once it slips."""
    assert value_after(arguments, "--temperature") == "0"
    assert value_after(arguments, "-mc") == "0"


def test_both_transcript_formats_are_requested(arguments):
    """The .txt is for reading, the .srt for subtitles and for jumping to a
    moment in the recording. Dropping either is a silent loss."""
    assert "-otxt" in arguments
    assert "-osrt" in arguments


def test_language_detection_is_automatic_but_overridable(arguments):
    assert value_after(arguments, "-l") == "auto"

    explicit = whisper.transcribe_arguments(
        audio=Path("/tmp/clip.wav"),
        output_stem=Path("/out/clip"),
        model=Path("/models/large.bin"),
        vad_model=Path("/models/vad.bin"),
        language="es",
    )
    assert value_after(explicit, "-l") == "es"


def test_the_output_prefix_carries_no_extension(arguments):
    """-of takes a stem: whisper-cli appends .txt and .srt itself. Passing a
    name with an extension produces clip.wav.txt."""
    assert value_after(arguments, "-of") == "/out/clip"
    assert whisper.outputs_for(Path("/out/clip")) == [Path("/out/clip.txt"), Path("/out/clip.srt")]


def test_audio_is_converted_to_what_whisper_works_in():
    """16 kHz mono is Whisper's internal format, and -vn drops the video stream:
    whisper-cli accepts neither a .mov nor 48 kHz stereo."""
    arguments = media.wav_arguments(Path("/in.mov"), Path("/out.wav"))
    assert value_after(arguments, "-ar") == "16000"
    assert value_after(arguments, "-ac") == "1"
    assert "-vn" in arguments
