"""Where output goes, and in what order the answer is decided (DESIGN.md 4.0)."""

from pathlib import Path

from cinta import config


def test_explicit_directory_wins(monkeypatch, tmp_path):
    """--output-dir is the most specific thing the user can say, so it beats a
    variable they set weeks ago and forgot."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "from-env"))
    assert config.output_dir(tmp_path / "explicit") == tmp_path / "explicit"


def test_environment_beats_config_file(monkeypatch, tmp_path):
    """An environment variable is set for one session on purpose; config.toml is
    the standing preference."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", str(tmp_path / "from-env"))
    monkeypatch.setattr(config, "load_config", lambda: {"output_dir": "/from/config"})
    assert config.output_dir() == tmp_path / "from-env"


def test_config_file_beats_the_default(monkeypatch):
    """The whole point of the config file: change where recordings land once."""
    monkeypatch.delenv("CINTA_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(config, "load_config", lambda: {"output_dir": "/from/config"})
    assert config.output_dir() == Path("/from/config")


def test_falls_back_to_the_cinta_directory(monkeypatch):
    """With nothing configured, output goes to ~/cinta (DESIGN.md 4.0). This is
    the path a fresh install uses, so it must not drift."""
    monkeypatch.delenv("CINTA_OUTPUT_DIR", raising=False)
    monkeypatch.setattr(config, "load_config", dict)
    assert config.output_dir() == Path.home() / "cinta"


def test_tildes_are_expanded(monkeypatch):
    """A shell expands ~ before the program sees it; an environment variable or a
    TOML string does not, and Path('~/x') would create a literal ~ directory."""
    monkeypatch.setenv("CINTA_OUTPUT_DIR", "~/somewhere")
    assert config.output_dir() == Path.home() / "somewhere"


def test_unreadable_config_is_ignored_rather_than_fatal(monkeypatch, tmp_path):
    """A typo in config.toml must not make the tool unusable. Losing a preference
    is recoverable; a CLI that refuses to start is not."""
    broken = tmp_path / "config.toml"
    broken.write_text("this is not = valid = toml")
    monkeypatch.setattr(config, "CONFIG_FILE", broken)
    assert config.load_config() == {}
