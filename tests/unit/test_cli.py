"""The root parser: how failures reach the shell."""

import pytest

from cinta import cli
from cinta.commands import devices
from cinta.errors import CintaError


def test_an_error_becomes_its_exit_code_and_prints_its_hint(monkeypatch, capsys):
    """Exit codes are the only thing a script can read. A CintaError escaping as
    a traceback would exit 1 and print noise, so both halves are asserted: the
    code the shell sees, and the advice the person sees."""

    def explode(args):
        raise CintaError("no such display", exit_code=12, hint="Run: cinta devices")

    monkeypatch.setattr(devices, "run", explode)

    assert cli.main(["devices"]) == 12
    captured = capsys.readouterr()
    assert "no such display" in captured.err
    assert "Run: cinta devices" in captured.err
    assert captured.out == ""


def test_no_command_prints_help_instead_of_failing(capsys):
    """Typing `cinta` alone is how people find out what a tool does. It must not
    be an error with no output."""
    assert cli.main([]) == 2
    assert "record" in capsys.readouterr().out


def test_interrupting_is_not_a_crash(monkeypatch):
    """Ctrl-C during a recording reaches this process too. 130 is the shell
    convention for it; a traceback would be wrong and ugly."""

    def interrupted(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(devices, "run", interrupted)
    assert cli.main(["devices"]) == 130


def test_an_unknown_command_is_rejected():
    """argparse exits rather than returning, and that exit has to be non-zero."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["transcribe"])
    assert exit_info.value.code != 0
