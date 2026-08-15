"""Executor registry, shared helpers, and no-shell guards (PR4, task 4.1).

Registry dispatch (design "Interfaces / Contracts"): intents are mapped to
handlers and dispatched from the orchestrator loop via ``execute(intent,
session)``; unregistered intents answer unsupported instead of crashing.
Shared subprocess/fs helpers keep every executor shell-free by construction
(threat matrix: no arbitrary shell), and a source scan guards the rule.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from jarvis.actions import assistant_lifecycle, base, files, opencode, system, web
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent
from jarvis.orchestrator.contracts import ActionResult

ACTIONS_SOURCES = (
    Path(base.__file__),
    Path(opencode.__file__),
    Path(system.__file__),
    Path(files.__file__),
    Path(web.__file__),
    Path(assistant_lifecycle.__file__),
)


def _intent(name="open_app", entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


# --- Registry dispatch -----------------------------------------------------
def test_registry_dispatches_to_registered_handler() -> None:
    registry = base.Registry()
    calls: list[tuple[str, object]] = []

    def handler(intent: Intent, session: object) -> ActionResult:
        calls.append((intent.intent, session))
        return ActionResult(ok=True, spoken="hecho")

    registry.register("help", handler)
    result = registry.execute(_intent("help"), {"session": 1})
    assert result.ok is True
    assert result.spoken == "hecho"
    assert calls == [("help", {"session": 1})]


def test_registry_unknown_intent_answers_unsupported() -> None:
    registry = base.Registry()
    registry.register("help", lambda intent, session: ActionResult(ok=True, spoken="ok"))
    result = registry.execute(_intent("open_app"), None)
    assert result.ok is False
    assert "no sé hacer eso" in result.spoken


def test_build_registry_covers_every_allowed_intent() -> None:
    registry = base.build_registry()
    assert set(registry.handlers()) == ALLOWED_INTENTS - {"unknown"}


def test_build_registry_marks_opencode_work_intents_long_running() -> None:
    registry = base.build_registry()
    assert registry.long_running_intents == {
        "ask",
        "create_artifact",
        "implement",
        "review",
    }


# --- Shared helpers --------------------------------------------------------
def test_exclusive_write_creates_new_file(tmp_path) -> None:
    path = tmp_path / "doc.md"
    base.exclusive_write(path, "hola\n")
    assert path.read_text() == "hola\n"


def test_exclusive_write_refuses_existing_file(tmp_path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("original")
    with pytest.raises(FileExistsError):
        base.exclusive_write(path, "nuevo")
    assert path.read_text() == "original"


def test_atomic_write_replaces_and_leaves_no_temp(tmp_path) -> None:
    path = tmp_path / "AGENTS.md"
    base.atomic_write(path, "v1")
    base.atomic_write(path, "v2")
    assert path.read_text() == "v2"
    assert not list(tmp_path.glob("*.tmp"))


def test_safe_run_returns_returncode_and_stderr() -> None:
    code, _ = base.safe_run(["true"])
    assert code == 0


def test_safe_run_reports_missing_command() -> None:
    code, _ = base.safe_run(["definitely-not-a-command-xyz"])
    assert code != 0


# --- Threat matrix guards (no arbitrary shell, single power_off_self) -------
def test_no_shell_or_os_system_in_any_executor() -> None:
    for source in ACTIONS_SOURCES:
        text = source.read_text()
        assert re.search(r"shell\s*=\s*True", text) is None, f"{source} enables a shell"
        assert re.search(r"os\.system\s*\(", text) is None, f"{source} uses os.system"


def test_power_off_self_defined_only_in_assistant_lifecycle() -> None:
    locations = [
        str(source)
        for source in ACTIONS_SOURCES
        if re.search(r"def power_off_self\s*\(", source.read_text())
    ]
    assert locations == [str(Path(assistant_lifecycle.__file__))]
