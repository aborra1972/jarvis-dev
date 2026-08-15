"""Session, active project and re-ask policy (PR3, task 3.3).

- RF-6: an active project is detected from ``git rev-parse --show-toplevel``
  of the current working directory, falling back to the last known value.
- RNF-4: after two re-asks the loop reveals the raw transcript (``reveal``).
- Debt WARNING #2: ``invalid_entity:*`` is a permanent rejection (spoken), it
  NEVER becomes valid by re-asking, so it is classified as ``rejected``
  without consuming a re-ask attempt.
- State persists atomically to ``STATE_FILE`` (PR3) so PR4/PR5 keep it.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from jarvis.interpreter import Interpretation
from jarvis.interpreter.schema import Intent

MAX_REASK_ATTEMPTS = 2

GitRunner = Callable[[str], str | None]


@dataclass(frozen=True)
class RepoSession:
    port: int
    session_work: str
    session_interp: str


@dataclass
class Session:
    active_project: str | None = None
    repos: dict[str, int] = field(default_factory=dict)
    reask_attempts: int = 0
    state_path: str = ""
    switched_off: bool = False
    work_sessions: dict[str, str] = field(default_factory=dict)
    _allocated: dict[str, RepoSession] = field(default_factory=dict)

    def bind_work_session(self, repo: str, session_id: str) -> None:
        """Remember the sessionID the server created for this repo (PR6).

        In-memory only: the id dies with the serve process, and a stale id
        degrades to the M4 spoken error on the next call.
        """
        self.work_sessions[repo] = session_id

    def start(self, cwd: str, git_runner: GitRunner) -> str | None:
        try:
            detected = git_runner(cwd)
        except Exception:
            detected = None
        if detected:
            self.active_project = detected
        return self.active_project

    def switch_active_project(self, repo: str) -> None:
        self.active_project = repo

    def resolve_repo(self, intent: Intent) -> str | None:
        if "app" in intent.entities:
            repo = intent.entities["app"]
            self.switch_active_project(repo)
            return repo
        return self.active_project

    def allocate(self, repo: str, base_port: int) -> RepoSession:
        if repo in self._allocated:
            return self._allocated[repo]
        index = self.repos.get(repo)
        if index is None:
            index = len(self.repos)
            self.repos[repo] = index
        allocated = RepoSession(
            port=base_port + index,
            session_work=str(uuid.uuid4()),
            session_interp=str(uuid.uuid4()),
        )
        self._allocated[repo] = allocated
        return allocated

    def next_step(self, interpretation: Interpretation) -> str:
        intent = interpretation.intent
        if intent is not None:
            self.reask_attempts = 0
            return "confirm" if intent.confirm_required else "execute"
        if interpretation.unsupported:
            self.reask_attempts = 0
            return "unsupported"
        if interpretation.reason.startswith("invalid_entity:"):
            self.reask_attempts = 0
            return "rejected"
        if interpretation.needs_reask:
            if self.reask_attempts >= MAX_REASK_ATTEMPTS:
                self.reask_attempts = 0
                return "reveal"
            self.reask_attempts += 1
            return "reask"
        return "ignore"

    def save(self) -> None:
        if not self.state_path:
            return
        payload = {
            "active_project": self.active_project,
            "repos": self.repos,
            "reask_attempts": self.reask_attempts,
            "switched_off": self.switched_off,
        }
        path = Path(self.state_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        os.replace(temp, path)


def load_state(path: str) -> Session:
    session = Session(state_path=path)
    file = Path(path)
    try:
        payload = json.loads(file.read_text())
    except (FileNotFoundError, ValueError):
        return session
    session.active_project = payload.get("active_project")
    session.repos = payload.get("repos", {})
    session.reask_attempts = payload.get("reask_attempts", 0)
    session.switched_off = payload.get("switched_off", False)
    return session
