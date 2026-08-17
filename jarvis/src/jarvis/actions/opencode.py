"""OpenCode executor (PR4, task 4.2): persistent serve lifecycle + run --attach.

Design (openspec "OpenCode Integration", ADR-1/ADR-8): one headless ``serve``
per repo, spawned on first use and reused while TCP-healthy; work commands
attach to the same sessionID. Repo paths are validated against shell
metacharacters (threat matrix: no arbitrary shell) and server degradation
degrades to a spoken error (M4) instead of crashing. Every subprocess call is
list-args; the launcher/prober/clock/runner are injectable so tests never
spawn real processes.
"""

from __future__ import annotations

import functools
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from jarvis import config
from jarvis.actions import base
from jarvis.interpreter.llm import (
    build_opencode_command,
    parse_assistant_text,
    parse_session_id,
)
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult
from jarvis.orchestrator.session import Session
from jarvis.orchestrator.supervisor import RealClock, tcp_healthy

OPCODE_INTENTS = ("open_repo", "ask", "configure", "create_artifact", "implement", "review")

# Verify fix (voice-pipeline "Long LLM operation"): the LLM work commands ride
# the persistent session and can take up to 30s, so the loop speaks an "En ello
# estoy, señor" acknowledgment before they run. Non-work commands are not long-running.
LONG_RUNNING_INTENTS = frozenset({"ask", "create_artifact", "implement", "review"})

NO_ACTIVE_PROJECT = "No hay un proyecto activo, señor. Abra uno primero."
OFFLINE_SPOKEN = "Necesito conexión a red para eso, señor."
_UNABLE_SPOKEN = "Lo lamento, señor, no pude completarlo. Intente de nuevo."
_SPOKEN_LIMIT = 300

# Rejects anything that could break out of a list-args command (threat matrix).
_REPO_UNSAFE = re.compile(r"[;|&$<>`'\"\\]")

_PROMPTS = {
    "ask": "Respondé con claridad: {q}",
    "create_artifact": "Creá un artefacto solicitado: {q}",
    "implement": "Implementá en este proyecto: {q}",
    "review": "Revisá este proyecto: {q}",
}


def resolve_repo_path(repo: str) -> Path | None:
    """Validate a repo reference; returns a canonical existing dir or None."""
    stripped = repo.strip()
    if not stripped or stripped.startswith("-"):
        return None
    if _REPO_UNSAFE.search(stripped):
        return None
    path = Path(stripped)
    if not path.is_dir():
        return None
    return path.resolve()


def _truncate(text: str, limit: int = _SPOKEN_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class ServerProcess:
    """Owns a spawned ``opencode serve`` subprocess (list-args, no shell)."""

    def __init__(self, process: subprocess.Popen) -> None:
        self._process = process

    def is_alive(self) -> bool:
        return self._process.poll() is None

    def stop(self) -> None:
        if self.is_alive():
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                # Process didn't die from SIGTERM — force kill
                self._process.kill()
                self._process.wait(timeout=3.0)


def _spawn_server(port: int, repo: Path, host: str) -> ServerProcess:
    process = subprocess.Popen(
        ["opencode", "serve", "--port", str(port), "--hostname", host],
        cwd=str(repo),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ServerProcess(process)


class ServerManager:
    """Spawn-once / reuse-while-healthy lifecycle for the per-repo serve."""

    def __init__(
        self,
        launcher: Callable[[int, Path], object],
        prober: Callable[[str, int, float], bool],
        clock: object,
        host: str = config.OPCODE_HOST,
        health_timeout: float = 0.2,
        poll_interval: float = 0.05,
        max_polls: int = 20,
        max_wait: float = 10.0,
    ) -> None:
        self._launcher = launcher
        self._prober = prober
        self._clock = clock
        self._host = host
        self._health_timeout = health_timeout
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._max_wait = max_wait

    def ensure_server(self, port: int, repo: Path) -> bool:
        """Reuse a healthy server or spawn + wait; True when healthy (M4)."""
        if self._prober(self._host, port, self._health_timeout):
            return True
        self._launcher(port, repo)
        deadline = self._clock.now() + self._max_wait
        polls = 0
        while polls < self._max_polls and self._clock.now() < deadline:
            polls += 1
            time.sleep(self._poll_interval)
            if self._prober(self._host, port, self._health_timeout):
                return True
        return False


class OpenCodeExecutor:
    """Executes the 6 opencode intents against the persistent serve."""

    def __init__(
        self,
        manager: ServerManager | None = None,
        runner: object | None = None,
        host: str = config.OPCODE_HOST,
        base_port: int = config.OPCODE_BASE_PORT,
        timeout: float = 30.0,
    ) -> None:
        self._host = host
        self._base_port = base_port
        self._timeout = timeout
        self._runner = runner or subprocess.run
        if manager is None:
            manager = ServerManager(
                launcher=functools.partial(_spawn_server, host=host),
                prober=tcp_healthy,
                clock=RealClock(),
            )
        self._manager = manager

    # open_repo owns project switching (loop delegates it here, PR4).
    def handle_open_repo(self, intent: Intent, session: Session) -> ActionResult:
        repo = (intent.entities.get("repo") or "").strip()
        if not repo:
            if not session.active_project:
                return ActionResult(ok=False, spoken=NO_ACTIVE_PROJECT)
            path = Path(session.active_project)
        else:
            path = resolve_repo_path(repo)
            if path is None:
                return ActionResult(ok=False, spoken=f"No puedo abrir eso, señor: {repo}")
        session.switch_active_project(str(path))
        allocated = session.allocate(str(path), self._base_port)
        if not self._manager.ensure_server(allocated.port, path):
            return ActionResult(ok=False, spoken=OFFLINE_SPOKEN)
        return ActionResult(ok=True, spoken=f"Abierto, señor: {path.name}")

    def handle_ask(self, intent: Intent, session: Session) -> ActionResult:
        return self._attached(intent, session)

    def handle_configure(self, intent: Intent, session: Session) -> ActionResult:
        if not session.active_project:
            return ActionResult(ok=False, spoken=NO_ACTIVE_PROJECT)
        base.atomic_write(Path(session.active_project) / "AGENTS.md", "project: jarvis")
        return ActionResult(ok=True, spoken="He configurado el proyecto, señor.")

    def handle_create_artifact(self, intent: Intent, session: Session) -> ActionResult:
        return self._attached(intent, session)

    def handle_implement(self, intent: Intent, session: Session) -> ActionResult:
        return self._attached(intent, session)

    def handle_review(self, intent: Intent, session: Session) -> ActionResult:
        return self._attached(intent, session)

    def _attached(self, intent: Intent, session: Session) -> ActionResult:
        if not session.active_project:
            return ActionResult(ok=False, spoken=NO_ACTIVE_PROJECT)
        allocated = session.allocate(session.active_project, self._base_port)
        prompt = _PROMPTS.get(intent.intent, "")
        query = (intent.entities.get("query") or "").strip()
        if query:
            prompt = prompt.format(q=query)
        # PR6 (integration): pass `-s` only once a server-created sessionID is
        # bound; the first run after serve spawn creates it (see llm.build_opencode_command).
        session_id = session.work_sessions.get(session.active_project)
        command = build_opencode_command(
            f"http://{self._host}:{allocated.port}",
            session_id,
            prompt,
            Path(session.active_project),
        )
        for _ in (1, 2):  # one retry before degrading (M4)
            try:
                result = self._runner(command, capture_output=True, text=True, timeout=self._timeout)
            except Exception:
                result = None
            if result is not None and result.returncode == 0:
                text = parse_assistant_text(result.stdout)
                if text:
                    if session_id is None:
                        created = parse_session_id(result.stdout)
                        if created:
                            session.bind_work_session(session.active_project, created)
                    return ActionResult(ok=True, spoken=_truncate(text), long_running=True)
        return ActionResult(ok=False, spoken=_UNABLE_SPOKEN)
