"""The zsh completion offers exactly what the parser accepts.

It is written by hand, so nothing else stops a new flag from being missing
from it, or a removed one from lingering.
"""

import argparse
import re
from pathlib import Path

import pytest

from cinta.cli import build_parser

SCRIPT = (Path(__file__).resolve().parents[2] / "completions" / "_cinta").read_text()


def subparsers() -> dict[str, argparse.ArgumentParser]:
    action = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    return dict(action.choices)


def section(command: str) -> str:
    match = re.search(rf"^\s+{command}\)\n(.*?)^\s+;;", SCRIPT, re.S | re.M)
    assert match, f"no completion section for {command}"
    return match.group(1)


def flags(text: str) -> set[str]:
    return set(re.findall(r"(?<![\w-])--[a-z][a-z-]*", text))


def parser_flags(parser: argparse.ArgumentParser) -> set[str]:
    return {o for a in parser._actions for o in a.option_strings if o.startswith("--")}


def test_the_same_commands():
    block = re.search(r"commands=\((.*?)\)\n", SCRIPT, re.S).group(1)
    offered = set(re.findall(r"'(\w+):", block))
    assert offered == set(subparsers())


def test_the_same_top_level_flags():
    top = SCRIPT[SCRIPT.index("_arguments -C") : SCRIPT.index("case $state")]
    assert flags(top) == parser_flags(build_parser())


@pytest.mark.parametrize("command", sorted(subparsers()))
def test_the_same_flags(command):
    assert flags(section(command)) == parser_flags(subparsers()[command])


@pytest.mark.parametrize("command", sorted(subparsers()))
def test_the_same_choices(command):
    for action in subparsers()[command]._actions:
        if action.choices and action.option_strings:
            flag = action.option_strings[-1]
            match = re.search(rf"{flag}\[[^]]*\]:[^:]*:\(([^)]*)\)", section(command))
            assert match, f"{command} {flag} does not complete its choices"
            assert set(match.group(1).split()) == set(action.choices)
