"""Getting the two model files onto the disk."""

from cinta import config
from cinta.core import models


def test_the_two_models_are_pinned_not_chosen():
    """There is deliberately no catalogue and no --model flag. What there must
    be is exactly the two files whisper-cli needs, from URLs that resolve to the
    file itself rather than to a HuggingFace web page."""
    assert len(models.ALL) == 2
    assert models.SPEECH.filename == "ggml-large-v3.bin"
    assert models.VAD.filename == "ggml-silero-v5.1.2.bin"
    for model in models.ALL:
        assert model.url.endswith(model.filename)
        assert "/resolve/main/" in model.url


def test_models_live_under_the_configured_output_directory(monkeypatch, tmp_path):
    """One cinta directory, not two: deleting ~/cinta has to take the models
    with it. A standing preference in config.toml moves both together."""
    monkeypatch.delenv("CINTA_MODELS_DIR", raising=False)
    monkeypatch.delenv("CINTA_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(config, "load_config", lambda: {"output_dir": str(tmp_path)})

    assert config.models_dir() == tmp_path / "models"
    assert models.path_for(models.SPEECH).parent == tmp_path / "models"


def test_an_existing_model_is_not_downloaded_again(monkeypatch, tmp_path):
    """Re-downloading 3 GB because a check was skipped is the expensive mistake
    this guards against."""
    monkeypatch.setenv("CINTA_MODELS_DIR", str(tmp_path))
    for model in models.ALL:
        (tmp_path / model.filename).write_bytes(b"already here")

    def refuse(*args, **kwargs):
        raise AssertionError("download attempted for a model that is already present")

    monkeypatch.setattr(models, "download", refuse)

    resolved = models.ensure_available()
    assert resolved[models.SPEECH.filename] == tmp_path / models.SPEECH.filename


def test_a_missing_model_is_downloaded(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_MODELS_DIR", str(tmp_path))
    asked = []

    def fake_download(model, target):
        asked.append(model.filename)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"downloaded")

    monkeypatch.setattr(models, "download", fake_download)

    models.ensure_available()
    assert asked == [models.SPEECH.filename, models.VAD.filename]


def test_a_different_output_directory_does_not_move_the_models(monkeypatch, tmp_path):
    """The models directory must not follow --output-dir or $CINTA_OUTPUT_DIR.

    Writing one recording to an external disk would otherwise relocate the model
    directory with it, find nothing there, and download 3 GB again. This was a
    real bug: the first end-to-end run of `transcribe URL` with a scratch output
    directory re-downloaded the whole model.
    """
    monkeypatch.delenv("CINTA_MODELS_DIR", raising=False)
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "somewhere-else"))
    monkeypatch.setattr(config, "load_config", dict)

    assert config.models_dir() == config.DEFAULT_OUTPUT_DIR / "models"


def test_the_models_directory_can_still_be_moved_on_purpose(monkeypatch, tmp_path):
    monkeypatch.setenv("CINTA_MODELS_DIR", str(tmp_path / "elsewhere"))
    assert config.models_dir() == tmp_path / "elsewhere"
