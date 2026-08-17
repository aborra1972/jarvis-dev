"""Session / active-project / re-ask tests (PR3, task 3.3).

Covers: active project detection (RF-6), re-ask ×2 then reveal (RNF-4),
invalid_entity → spoken rejection without re-ask (debt WARNING #2), repo
allocation from base port, and atomic JSON persistence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jarvis.interpreter import Interpretation
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.session import RepoSession, Session, load_state


def _intent(**overrides) -> Intent:
    kwargs = {"intent": "open_app", "entities": {}, "confidence": 0.9, "confirm_required": False}
    kwargs.update(overrides)
    return Intent(**kwargs)


def _interp(**overrides) -> Interpretation:
    kwargs = {"intent": None, "needs_reask": False, "unsupported": False, "reason": ""}
    kwargs.update(overrides)
    return Interpretation(**kwargs)


def test_load_state_returns_fresh_when_missing(tmp_path: Path) -> None:
    session = load_state(tmp_path / "nope.json")
    assert session.active_project is None
    assert session.repos == {}
    assert session.reask_attempts == 0


def test_load_state_recovers_corrupt_json_as_fresh(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{ not json")
    session = load_state(path)
    assert session.active_project is None


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    session = load_state(path)
    session.active_project = "/repo/a"
    session.reask_attempts = 1
    session.repos = {"firefox": 0}
    session.switched_off = True
    session.save()

    loaded = load_state(path)
    assert loaded.active_project == "/repo/a"
    assert loaded.reask_attempts == 1
    assert loaded.repos == {"firefox": 0}
    assert loaded.switched_off is True


def test_save_is_atomic_no_temp_left(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    session = load_state(path)
    session.active_project = "/repo/b"
    session.save()
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads(path.read_text())["active_project"] == "/repo/b"


def test_start_detects_active_project_via_git(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    root = session.start(str(tmp_path), lambda cwd: "/detected/repo")
    assert session.active_project == "/detected/repo"
    assert root == "/detected/repo"


def test_start_keeps_last_known_when_git_fails(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    session = load_state(path)
    session.active_project = "/last/known"
    session.save()

    def failing_git(cwd: str) -> str | None:
        raise FileNotFoundError("no git")

    reloaded = load_state(path)
    assert reloaded.start(str(tmp_path), failing_git) == "/last/known"


def test_switch_active_project(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    session.switch_active_project("firefox")
    assert session.active_project == "firefox"


def test_resolve_repo_explicit_app_returns_app(tmp_path: Path) -> None:
    """resolve_repo returns the app entity without mutating active_project."""
    session = load_state(tmp_path / "state.json")
    intent = _intent(entities={"app": "firefox"})
    assert session.resolve_repo(intent) == "firefox"
    # M3 fix: resolve_repo no longer mutates active_project
    assert session.active_project is None


def test_resolve_repo_uses_active_project(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    session.active_project = "firefox"
    assert session.resolve_repo(_intent(use_active_project=True)) == "firefox"


def test_resolve_repo_none_without_context(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    assert session.resolve_repo(_intent()) is None


def test_allocate_assigns_ports_and_session_ids(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    first = session.allocate("firefox", base_port=32111)
    second = session.allocate("firefox", base_port=32111)
    third = session.allocate("chromium", base_port=32111)
    assert isinstance(first, RepoSession)
    assert first.port == 32111
    assert second.port == 32111
    assert third.port == 32112
    assert first.session_work != first.session_interp
    assert first.session_work == second.session_work


def test_next_step_executes_plain_intent(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    session.reask_attempts = 2
    assert session.next_step(_interp(intent=_intent())) == "execute"
    assert session.reask_attempts == 0


def test_next_step_confirms_destructive_intent(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    intent = _intent(intent="shutdown", confirm_required=True)
    assert session.next_step(_interp(intent=intent)) == "confirm"


def test_next_step_unsupported_resets(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    session.reask_attempts = 1
    assert session.next_step(_interp(unsupported=True, reason="unknown_intent")) == "unsupported"
    assert session.reask_attempts == 0


def test_next_step_invalid_entity_rejects_without_reask(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    session.reask_attempts = 1
    interp = _interp(needs_reask=True, reason="invalid_entity:app")
    assert session.next_step(interp) == "rejected"
    assert session.reask_attempts == 0


def test_next_step_reask_then_reveal_after_two(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    interp = _interp(needs_reask=True, reason="low_confidence")
    assert session.next_step(interp) == "reask"
    assert session.reask_attempts == 1
    assert session.next_step(interp) == "reask"
    assert session.reask_attempts == 2
    assert session.next_step(interp) == "reveal"
    assert session.reask_attempts == 0


def test_next_step_ignore_on_unknown(tmp_path: Path) -> None:
    session = load_state(tmp_path / "state.json")
    assert session.next_step(_interp(needs_reask=False, reason="llm_failure")) == "ignore"
