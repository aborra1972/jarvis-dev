"""Orchestrator dependency contracts (PR3).

Minimal protocols the orchestrator consumes so PR4 (executors) and PR5
(voice) implement against them without rework. The loop wires concrete
adapters; tests drive fakes. ``Clock`` is injectable everywhere time matters
(confirm 15s, supervisor backoff).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Callable, Protocol

from jarvis.interpreter.schema import Intent


class Clock(Protocol):
    def now(self) -> float: ...


class WakeDetector(Protocol):
    def wait(self, timeout: float) -> bool: ...


class Capture(Protocol):
    def capture(self) -> str | None: ...


class OperationToken:
    """Loop-owned generation token used to reject work after invalidation."""

    _generations = count(1)

    def __init__(self, generation: int | None = None) -> None:
        self.generation = generation if generation is not None else next(self._generations)
        self._cancelled = False
        self.reason: str | None = None

    @classmethod
    def next(cls) -> "OperationToken":
        return cls()

    def cancel(self, reason: str = "cancelled") -> None:
        self._cancelled = True
        self.reason = reason

    def cancelled(self) -> bool:
        return self._cancelled

    def is_current(self, current: "OperationToken") -> bool:
        return not self.cancelled() and self.generation == current.generation


class CaptureError(Exception):
    """Capture/STT hardware failure — the loop replies with a spoken error (PR6).

    Distinct from ``None`` (silence → stay idle): an error is abnormal, so the
    loop tells the human and retries instead of pretending nothing was heard.
    """


class PromptCompletion(Protocol):
    """Verified evidence that a specific prompt finished playing."""

    @property
    def completed(self) -> bool: ...


class Speaker(Protocol):
    def speak(self, text: str) -> None: ...

    # Optional adapter: confirmation must use this seam when playback is async.
    def speak_and_wait(self, text: str) -> PromptCompletion: ...


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    spoken: str
    data: dict = field(default_factory=dict)
    # Verify fix (voice-pipeline "Long LLM operation"): marks an operation the
    # executor estimates over 3s (LLM/OpenCode work commands) so consumers can
    # branch on it; the loop reads the registry's long_running_intents to speak
    # the acknowledgment BEFORE calling execute().
    long_running: bool = False


class Executor(Protocol):
    def execute(self, intent: Intent, session: object) -> ActionResult: ...


Interpreter = Callable[[str], object]
