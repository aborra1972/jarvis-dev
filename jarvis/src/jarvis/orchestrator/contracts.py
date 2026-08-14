"""Orchestrator dependency contracts (PR3).

Minimal protocols the orchestrator consumes so PR4 (executors) and PR5
(voice) implement against them without rework. The loop wires concrete
adapters; tests drive fakes. ``Clock`` is injectable everywhere time matters
(confirm 15s, supervisor backoff).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from jarvis.interpreter.schema import Intent


class Clock(Protocol):
    def now(self) -> float: ...


class WakeDetector(Protocol):
    def wait(self, timeout: float) -> bool: ...


class Capture(Protocol):
    def capture(self) -> str | None: ...


class CaptureError(Exception):
    """Capture/STT hardware failure — the loop replies with a spoken error (PR6).

    Distinct from ``None`` (silence → stay idle): an error is abnormal, so the
    loop tells the human and retries instead of pretending nothing was heard.
    """


class Speaker(Protocol):
    def speak(self, text: str) -> None: ...


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    spoken: str
    data: dict = field(default_factory=dict)


class Executor(Protocol):
    def execute(self, intent: Intent, session: object) -> ActionResult: ...


Interpreter = Callable[[str], object]
