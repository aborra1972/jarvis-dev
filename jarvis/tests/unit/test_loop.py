"""Orchestrator loop tests (PR3, task 3.5).

Drives the full FSM with fakes: wake, capture (voice transcripts), scripted
interpreter, speaker, and executor. Covers the design sequence diagrams:
execute path, confirm yes/no/timeout (M6), re-ask ×2 → reveal (RNF-4),
invalid_entity → spoken rejection without re-ask (debt WARNING #2), silence,
switch off/on (RF-11), and power_off_self → stopped.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from jarvis.interpreter import Interpretation
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult
from jarvis.orchestrator.loop import (
    REASK_1,
    REASK_2,
    REJECTED_SPOKEN,
    REVEAL_PREFIX,
    UNSUPPORTED_SPOKEN,
    Pipeline,
    run,
)
from jarvis.orchestrator.session import Session, load_state


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def advance(self, delta: float) -> None:
        self.t += delta


class FakeWake:
    def __init__(self, results: list[bool]) -> None:
        self.results = deque(results)

    def wait(self, timeout: float) -> bool:
        return self.results.popleft() if self.results else False


class FakeCapture:
    def __init__(self, transcripts: list[str | None], clock: FakeClock | None = None, advance: float = 0.0) -> None:
        self.transcripts = deque(transcripts)
        self.clock = clock
        self.advance = advance

    def capture(self) -> str | None:
        if self.clock is not None:
            self.clock.advance(self.advance)
        return self.transcripts.popleft() if self.transcripts else None


class FakeSpeaker:
    def __init__(self) -> None:
        self.said: list[str] = []

    def speak(self, text: str) -> None:
        self.said.append(text)


class FakeInterpreter:
    def __init__(self, script: list[Interpretation]) -> None:
        self.script = deque(script)
        self.calls: list[str] = []

    def __call__(self, text: str) -> Interpretation:
        self.calls.append(text)
        return self.script.popleft() if self.script else Interpretation()


class FakeExecutor:
    def __init__(self, results: dict[str, ActionResult] | None = None) -> None:
        self.calls: list[Intent] = []
        self.results = results or {}

    def execute(self, intent: Intent, session: object) -> ActionResult:
        self.calls.append(intent)
        return self.results.get(intent.intent, ActionResult(ok=True, spoken="ok"))


def _intent(**overrides) -> Intent:
    kwargs = {"intent": "open_app", "entities": {"app": "firefox"}, "confidence": 0.9, "confirm_required": False}
    kwargs.update(overrides)
    return Intent(**kwargs)


def _interp(intent: Intent | None = None, **overrides) -> Interpretation:
    kwargs = {"intent": intent, "needs_reask": False, "unsupported": False, "reason": ""}
    kwargs.update(overrides)
    return Interpretation(**kwargs)


def _pipeline(
    *,
    wake: list[bool],
    transcripts: list[str | None],
    interpreter_script: list[Interpretation],
    executor=None,
    clock: FakeClock | None = None,
    session: Session | None = None,
    switch_state=None,
    tmp_path: Path | None = None,
) -> Pipeline:
    path = tmp_path / "state.json" if tmp_path is not None else "/tmp/state.json"
    return Pipeline(
        clock=clock or FakeClock(),
        wake=FakeWake(wake),
        capture=FakeCapture(transcripts, clock=clock, advance=16.0 if clock is not None else 0.0),
        interpreter=FakeInterpreter(interpreter_script),
        speaker=FakeSpeaker(),
        executor=executor or FakeExecutor(),
        session=session or load_state(str(path)),
        cwd=str(tmp_path or "/tmp"),
        git_runner=lambda cwd: "/repo",
        switch_state=switch_state,
    )


def test_executes_open_app_cycle(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["abrí firefox"],
        interpreter_script=[_interp(_intent())],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert [c.intent for c in pipeline.executor.calls] == ["open_app"]
    assert isinstance(pipeline.speaker.said[-1], str)


def test_confirm_yes_executes_shutdown(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["apagá el sistema", "sí"],
        interpreter_script=[_interp(_intent(intent="shutdown", confirm_required=True))],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=5)
    assert outcome == "executed"
    assert [c.intent for c in pipeline.executor.calls] == ["shutdown"]


def test_confirm_no_aborts_without_executing(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["apagá el sistema", "no"],
        interpreter_script=[_interp(_intent(intent="shutdown", confirm_required=True))],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "aborted"
    assert pipeline.executor.calls == []
    assert "cancel" in pipeline.speaker.said[-1]


def test_confirm_silence_times_out(tmp_path: Path) -> None:
    clock = FakeClock()
    pipeline = _pipeline(
        wake=[True],
        transcripts=["apagá el sistema"],
        interpreter_script=[_interp(_intent(intent="reboot", confirm_required=True))],
        clock=clock,
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "timed_out"
    assert pipeline.executor.calls == []
    assert "no confirmaste" in pipeline.speaker.said[-1]


def test_reask_twice_then_reveal_transcript(tmp_path: Path) -> None:
    low = _interp(needs_reask=True, reason="low_confidence")
    pipeline = _pipeline(
        wake=[True],
        transcripts=["abrí firefox", "abrí firefox", "abrí firefox"],
        interpreter_script=[low, low, low],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=5)
    assert outcome == "revealed"
    said = pipeline.speaker.said
    assert any(REASK_1 in s for s in said)
    assert any(REASK_2 in s for s in said)
    assert any(REVEAL_PREFIX in s and "abrí firefox" in s for s in said)


def test_invalid_entity_rejected_without_reask(tmp_path: Path) -> None:
    invalid = _interp(needs_reask=True, reason="invalid_entity:app")
    pipeline = _pipeline(
        wake=[True],
        transcripts=["abrí la app mala"],
        interpreter_script=[invalid],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=3)
    assert outcome == "rejected"
    assert REJECTED_SPOKEN in pipeline.speaker.said[-1]
    assert pipeline.session.reask_attempts == 0
    assert not any(REASK_1 in s for s in pipeline.speaker.said)


def test_unsupported_spoken(tmp_path: Path) -> None:
    unsupported = _interp(unsupported=True, reason="unknown_intent")
    pipeline = _pipeline(
        wake=[True],
        transcripts=["hacé cualquier cosa"],
        interpreter_script=[unsupported],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=3)
    assert outcome == "unsupported"
    assert UNSUPPORTED_SPOKEN in pipeline.speaker.said[-1]


def test_silence_returns_to_idle(tmp_path: Path) -> None:
    pipeline = _pipeline(wake=[True], transcripts=[None], interpreter_script=[], tmp_path=tmp_path)
    outcome = run(pipeline, iterations=2)
    assert outcome == "silence"


def test_no_wake(tmp_path: Path) -> None:
    pipeline = _pipeline(wake=[False], transcripts=[], interpreter_script=[], tmp_path=tmp_path)
    assert run(pipeline, iterations=1) == "no_wake"


def test_power_off_self_stops_loop(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["jarvis, apagate", "sí"],
        interpreter_script=[_interp(_intent(intent="power_off_self", confirm_required=True))],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=50)
    assert outcome == "powered_off"
    assert [c.intent for c in pipeline.executor.calls] == ["power_off_self"]


class FakeSwitch:
    def __init__(self, on_for: int = 1) -> None:
        self.calls = 0
        self.on_for = on_for

    def __call__(self) -> bool:
        self.calls += 1
        return self.calls <= self.on_for


def test_switch_off_ignores_wake_then_resumes(tmp_path: Path) -> None:
    switch = FakeSwitch(on_for=1)
    session = load_state(str(tmp_path / "state.json"))
    session.switched_off = True
    pipeline = _pipeline(
        wake=[True, True],
        transcripts=["abrí firefox"],
        interpreter_script=[_interp(_intent())],
        session=session,
        switch_state=switch,
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=6)
    assert outcome == "executed"
    assert [c.intent for c in pipeline.executor.calls] == ["open_app"]
    assert switch.calls >= 2


def test_persists_session_state_after_run(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["abrí firefox"],
        interpreter_script=[_interp(_intent(entities={"app": "chromium"}))],
        tmp_path=tmp_path,
    )
    run(pipeline, iterations=4)
    reloaded = load_state(str(tmp_path / "state.json"))
    assert reloaded.active_project == "chromium"
    assert reloaded.repos == {"chromium": 0}
