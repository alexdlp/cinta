"""cinta devices: the listing people read before recording."""

import json

from cinta.cli import main


def test_screens_and_microphones_are_listed_with_the_number_you_type(fake_recorder, capsys):
    """The number shown has to be the number --display accepts. If the listing
    printed the display id instead, every instruction it gives would be wrong:
    on this arrangement id 1 and index 1 are different screens."""
    assert main(["devices"]) == 0

    output = capsys.readouterr().out
    assert "1  Mi Monitor" in output
    assert "3  Built-in Retina Display" in output
    assert "(main)" in output
    assert "1  MacBook Pro Microphone" in output
    assert "(default)" in output


def test_windows_are_not_offered_as_targets(fake_recorder, capsys):
    """cintarec enumerates windows, but recording one is not implemented. The
    fixture includes a Safari window precisely so this can assert it is absent:
    listing a target that cannot be used is worse than listing nothing."""
    assert main(["devices"]) == 0
    assert "Safari" not in capsys.readouterr().out


def test_json_mode_passes_the_payload_through(fake_recorder, capsys):
    """Scripts get everything, including the windows the human listing hides, and
    they get it as parseable JSON rather than the table."""
    assert main(["--json", "devices"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["displays"][0]["name"] == "Mi Monitor"
    assert payload["windows"][0]["app"] == "Safari"
