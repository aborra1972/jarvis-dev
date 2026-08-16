"""OpenCode executor (PR4, task 4.2): persistent serve lifecycle + run --attach.

Design (openspec "OpenCode Integration" + ADR-1/ADR-8): a per-repo headless
``serve`` is spawned on first use and reused while TCP-healthy; run commands
attach to the same sessionID. Repo paths are validated (no shell metachar
injection, threat matrix), and server degradation degrades to a spoken error
(M4) instead of crashing. All subprocess is list-args; the runner is
injectable so tests never spawn real processes.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from jarvis.actions import base, opencode
from jarvis.config import OPCODE_BASE_PORT, OPCODE_HOST
from jarvis.interpreter.llm import build_opencode_command, parse_assistant_text
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult
from jarvis.orchestrator.session import Session


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


class FakeRunner:
    def __init__(self, *results) -> None:
        self.results = list(results)
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        if not self.results:
            raise RuntimeError("fake runner exhausted")
        return self.results.pop(0)


class FakeManager:
    def __init__(self, healthy=True) -> None:
        self.healthy = healthy
        self.calls: list[tuple[int, Path]] = []

    def ensure_server(self, port: int, repo: Path) -> bool:
        self.calls.append((port, repo))
        return self.healthy


def _result(stdout: str, returncode: int = 0):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


def _assistant(text: str, session_id: str | None = None) -> str:
    import json

    event: dict = {
        "type": "message",
        "message": {"role": "assistant", "parts": [{"type": "text", "text": text}]},
    }
    if session_id:
        event["sessionID"] = session_id
    return json.dumps(event)


# --- resolve_repo_path (threat matrix: no shell metachar injection) ----------
def test_resolve_repo_path_rejects_empty() -> None:
    assert opencode.resolve_repo_path("") is None
    assert opencode.resolve_repo_path("   ") is None


def test_resolve_repo_path_rejects_leading_dash(tmp_path) -> None:
    assert opencode.resolve_repo_path("-flag") is None


@pytest.mark.parametrize(
    "repo",
    [
        ";rm -rf /",
        "repo; echo pwned",
        "a|b",
        "a&b",
        "a$(whoami)",
        "a`id`",
        'a"b',
        "a'b",
        "a\\b",
        "a<in",
        "a>out",
    ],
)
def test_resolve_repo_path_rejects_shell_metachars(repo) -> None:
    assert opencode.resolve_repo_path(repo) is None


def test_resolve_repo_path_rejects_missing_directory() -> None:
    assert opencode.resolve_repo_path("/no/such/repo/anywhere") is None


def test_resolve_repo_path_accepts_existing_directory(tmp_path) -> None:
    resolved = opencode.resolve_repo_path(str(tmp_path))
    assert resolved == Path(str(tmp_path))


# --- ServerManager lifecycle -------------------------------------------------
class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t


class FakeProber:
    def __init__(self, healthy_after: dict[tuple[str, int], int] | None = None) -> None:
        self.healthy_after = healthy_after or {}
        self.polls = 0

    def __call__(self, host: str, port: int, timeout: float) -> bool:
        self.polls += 1
        count = self.healthy_after.get((host, port), 0)
        return count > 0 and self.polls >= count


class FakeServer:
    def __init__(self) -> None:
        self.stops = 0

    def is_alive(self) -> bool:
        return True

    def stop(self) -> None:
        self.stops += 1


def test_server_manager_reuses_healthy_existing_server() -> None:
    launched = []
    manager = opencode.ServerManager(
        launcher=lambda port, repo: launched.append(port) or FakeServer(),
        prober=lambda host, port, timeout: True,
        clock=FakeClock(),
    )
    assert manager.ensure_server(32111, Path("/repo")) is True
    assert launched == []


def test_server_manager_spawns_when_not_healthy() -> None:
    launched = []
    manager = opencode.ServerManager(
        launcher=lambda port, repo: launched.append((port, str(repo))) or FakeServer(),
        prober=FakeProber(healthy_after={("127.0.0.1", 32111): 2}),
        clock=FakeClock(),
    )
    assert manager.ensure_server(32111, Path("/repo")) is True
    assert launched == [(32111, "/repo")]


def test_server_manager_degrades_when_never_healthy() -> None:
    manager = opencode.ServerManager(
        launcher=lambda port, repo: FakeServer(),
        prober=lambda host, port, timeout: False,
        clock=FakeClock(),
    )
    assert manager.ensure_server(32111, Path("/repo")) is False


# --- handle_open_repo --------------------------------------------------------
def test_open_repo_without_repo_and_without_active_project() -> None:
    executor = opencode.OpenCodeExecutor(manager=FakeManager())
    result = executor.handle_open_repo(_intent("open_repo"), Session())
    assert result.ok is False
    assert result.spoken == opencode.NO_ACTIVE_PROJECT


def test_open_repo_with_unsafe_repo_never_runs(tmp_path) -> None:
    manager = FakeManager()
    executor = opencode.OpenCodeExecutor(manager=manager)
    session = Session()
    result = executor.handle_open_repo(_intent("open_repo", {"repo": ";rm -rf /"}), session)
    assert result.ok is False
    assert manager.calls == []
    assert session.active_project is None


def test_open_repo_with_explicit_repo_switches_and_allocates(tmp_path) -> None:
    manager = FakeManager()
    executor = opencode.OpenCodeExecutor(manager=manager)
    session = Session()
    result = executor.handle_open_repo(_intent("open_repo", {"repo": str(tmp_path)}), session)
    assert result.ok is True
    assert "Abierto" in result.spoken
    assert session.active_project == str(tmp_path)
    assert manager.calls == [(OPCODE_BASE_PORT, Path(str(tmp_path)))]


def test_open_repo_degrades_when_server_unhealthy(tmp_path) -> None:
    executor = opencode.OpenCodeExecutor(manager=FakeManager(healthy=False))
    session = Session()
    result = executor.handle_open_repo(_intent("open_repo", {"repo": str(tmp_path)}), session)
    assert result.ok is False
    assert result.spoken == opencode.OFFLINE_SPOKEN


# --- run intents (ask/create_artifact/implement/review/configure) -------------
def test_ask_requires_active_project() -> None:
    executor = opencode.OpenCodeExecutor(manager=FakeManager())
    result = executor.handle_ask(_intent("ask", {"query": "hola"}), Session())
    assert result.ok is False
    assert result.spoken == opencode.NO_ACTIVE_PROJECT


def test_ask_first_call_omits_session_and_binds_server_session_id(tmp_path) -> None:
    # PR6 (integration): a fresh server has no session yet, so the first run
    # MUST NOT pass `-s` (opencode errors "Session not found"); the sessionID
    # from the NDJSON stream is bound for later calls.
    runner = FakeRunner(_result(_assistant("hola, ¿en qué te ayudo?", session_id="ses_xyz")))
    executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
    session = Session()
    session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
    result = executor.handle_ask(_intent("ask", {"query": "¿cómo estás?"}), session)
    assert result.ok is True
    assert result.spoken == "hola, ¿en qué te ayudo?"
    command = runner.commands[0]
    assert command[:4] == [
        "opencode", "run", "--attach",
        f"http://{OPCODE_HOST}:{OPCODE_BASE_PORT}",
    ]
    assert "-s" not in command
    assert session.work_sessions[session.active_project] == "ses_xyz"
    assert "--dir" in command


def test_ask_reuses_bound_session_on_subsequent_calls(tmp_path) -> None:
    runner = FakeRunner(
        _result(_assistant("primera", session_id="ses_abc")),
        _result(_assistant("segunda")),
    )
    executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
    session = Session()
    session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
    assert executor.handle_ask(_intent("ask", {"query": "primera"}), session).ok is True
    assert executor.handle_ask(_intent("ask", {"query": "segunda"}), session).ok is True
    second = runner.commands[1]
    assert second[second.index("-s") + 1] == "ses_abc"


def test_ask_truncates_long_spoken_text(tmp_path) -> None:
    long_text = "x" * 500
    runner = FakeRunner(_result(_assistant(long_text)))
    executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
    session = Session()
    session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
    result = executor.handle_ask(_intent("ask", {"query": "?"}), session)
    assert result.ok is True
    assert len(result.spoken) <= 300
    assert result.spoken.endswith("...")


def test_ask_retries_once_then_degrades(tmp_path) -> None:
    runner = FakeRunner(_result("", returncode=1), _result("", returncode=1))
    executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
    session = Session()
    session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
    result = executor.handle_ask(_intent("ask", {"query": "?"}), session)
    assert result.ok is False
    assert len(runner.commands) == 2


def test_run_intent_builds_opencode_command_per_intent(tmp_path) -> None:
    for intent_name in ("create_artifact", "implement", "review"):
        runner = FakeRunner(_result(_assistant("listo")))
        executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
        session = Session()
        session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
        result = executor.handle_create_artifact(
            _intent(intent_name), session
        ) if intent_name == "create_artifact" else executor.handle_implement(
            _intent(intent_name), session
        ) if intent_name == "implement" else executor.handle_review(
            _intent(intent_name), session
        )
        assert result.ok is True
        assert result.spoken == "listo"
        assert runner.commands[0][0] == "opencode"


def test_configure_writes_agents_md_and_does_not_run_subprocess(tmp_path, monkeypatch) -> None:
    written = []
    monkeypatch.setattr(
        opencode.base,
        "atomic_write",
        lambda path, content: written.append((str(path), content)),
    )
    runner = FakeRunner()
    executor = opencode.OpenCodeExecutor(manager=FakeManager(), runner=runner)
    session = Session()
    session.start(str(tmp_path), git_runner=lambda cwd: str(tmp_path))
    result = executor.handle_configure(_intent("configure"), session)
    assert result.ok is True
    assert written == [(str(Path(str(tmp_path)) / "AGENTS.md"), "project: jarvis")]
    assert runner.commands == []
