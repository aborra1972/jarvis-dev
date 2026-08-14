"""Bootstrap smoke tests (PR1).

Verifies the skeleton contract: every package module imports, stub callables
fail loudly (NotImplementedError) until their PR lands, the CLI surfaces the
six lifecycle commands, and config exposes the wired spike paths/ports.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import pytest

import jarvis
import jarvis.cli
import jarvis.config

# Every skeleton module must import (design Repo Structure).
SKELETON_MODULES = (
    "jarvis",
    "jarvis.audio",
    "jarvis.wake",
    "jarvis.stt",
    "jarvis.tts",
    "jarvis.cli",
    "jarvis.config",
    "jarvis.interpreter",
    "jarvis.interpreter.normalize",
    "jarvis.interpreter.golden",
    "jarvis.interpreter.llm",
    "jarvis.interpreter.schema",
    "jarvis.orchestrator",
    "jarvis.orchestrator.state",
    "jarvis.orchestrator.confirm",
    "jarvis.orchestrator.session",
    "jarvis.orchestrator.supervisor",
    "jarvis.orchestrator.loop",
    "jarvis.actions",
    "jarvis.actions.base",
    "jarvis.actions.opencode",
    "jarvis.actions.system",
    "jarvis.actions.files",
    "jarvis.actions.web",
    "jarvis.actions.assistant_lifecycle",
)

# Stub callables must raise until their PR lands (fail loud, no fake logic).
# NOTE (PR2): the four interpreter stubs were implemented in PR2 and their
# stub entries removed — behavior is covered by tests/unit/test_normalize.py,
# test_golden.py, test_schema.py, test_llm.py, test_interpreter.py.
# NOTE (PR3): the orchestrator stubs (state, confirm, session, supervisor,
# loop) were implemented in PR3 and removed — covered by tests/unit/test_state.py,
# test_confirm.py, test_session.py, test_supervisor.py, test_loop.py.
STUB_CALLABLES = (
    "jarvis.audio.capture",
    "jarvis.wake.detect",
    "jarvis.stt.transcribe",
    "jarvis.tts.speak",
)

CLI_COMMANDS = ("start", "stop", "off", "on", "clean", "logs")
# Wired in PR3 (start/off/on) or still a skeleton until PR6.
CLI_STUBS = ("stop", "clean", "logs")


def _resolve(dotted: str):
    module_name, _, attr = dotted.rpartition(".")
    return getattr(importlib.import_module(module_name), attr)


# --- Package -----------------------------------------------------------------
def test_package_version() -> None:
    assert isinstance(jarvis.__version__, str)
    assert jarvis.__version__


@pytest.mark.parametrize("module", SKELETON_MODULES)
def test_skeleton_module_imports(module: str) -> None:
    importlib.import_module(module)


@pytest.mark.parametrize("dotted", STUB_CALLABLES)
def test_stub_fails_until_logic_lands(dotted: str) -> None:
    with pytest.raises(NotImplementedError):
        _resolve(dotted)()


# --- CLI ---------------------------------------------------------------------
def test_cli_parser_exposes_lifecycle_commands() -> None:
    parser = jarvis.cli.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    subparsers = {a.dest: a for a in parser._actions if isinstance(a, argparse._SubParsersAction)}
    actions = subparsers["command"].choices
    assert set(actions) == set(CLI_COMMANDS)


@pytest.mark.parametrize("cmd", CLI_STUBS)
def test_cli_subcommand_is_a_stub(cmd: str, capsys: pytest.CaptureFixture) -> None:
    assert jarvis.cli.main([cmd]) == 1
    assert "not implemented yet" in capsys.readouterr().err


def test_cli_start_wires_orchestrator(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(jarvis.config, "STATE_FILE", tmp_path / "state.json")
    assert jarvis.cli.main(["start"]) == 1
    assert "skeleton" in capsys.readouterr().err


def test_cli_off_sets_switch_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(jarvis.config, "STATE_FILE", tmp_path / "state.json")
    assert jarvis.cli.main(["off"]) == 0
    assert (tmp_path / "state.json").exists()
    assert capsys.readouterr().err  # non-silent switch feedback
    assert jarvis.cli.main(["on"]) == 0


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        jarvis.cli.build_parser().parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_no_args_prints_help_and_exits_zero(capsys: pytest.CaptureFixture) -> None:
    assert jarvis.cli.main([]) == 0
    assert "jarvis" in capsys.readouterr().out


# --- Config ------------------------------------------------------------------
def test_config_wires_spike_artifacts() -> None:
    for attr in ("SPIKE", "WHISPER_CLI", "WHISPER_MODEL", "PIPER_BIN", "PIPER_MODEL", "PIPER_CONFIG"):
        assert isinstance(getattr(jarvis.config, attr), Path)


def test_config_wires_server_ports() -> None:
    assert jarvis.config.OPCODE_HOST == "127.0.0.1"
    assert isinstance(jarvis.config.OPCODE_BASE_PORT, int)
    assert jarvis.config.OPCODE_BASE_PORT > 0
    assert isinstance(jarvis.config.STATE_FILE, Path)


def test_config_wires_allowlists_and_prompt_placeholders() -> None:
    assert isinstance(jarvis.config.ALLOWED_APPS, set)
    assert isinstance(jarvis.config.INTERPRETER_SYSTEM_PROMPT, str)


# --- Fixtures -----------------------------------------------------------------
def test_fixtures_dir_fixture(fixtures_dir: Path) -> None:
    assert fixtures_dir.name == "fixtures"
    assert fixtures_dir.is_dir()
