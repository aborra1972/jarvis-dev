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
    LONG_OPERATION_ACK,
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


class TrackingExecutor:
    """Records what the speaker had already said when execute() ran (order)."""

    def __init__(
        self,
        speaker: FakeSpeaker,
        result: ActionResult,
        long_running: frozenset[str] = frozenset(),
    ) -> None:
        self.speaker = speaker
        self.result = result
        self.long_running_intents = long_running
        self.spoken_before_execute: list[str] = []

    def execute(self, intent: Intent, session: object) -> ActionResult:
        self.spoken_before_execute = list(self.speaker.said)
        return self.result


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
    assert "Cancelo" in pipeline.speaker.said[-1]


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
    assert "No confirmó a tiempo" in pipeline.speaker.said[-1]


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


class FakeTranscriptLog:
    def __init__(self) -> None:
        self.records: list[tuple[str, str | None, str]] = []

    def record(self, transcript: str, intent=None, outcome=None) -> None:
        self.records.append((transcript, intent, outcome))


def test_loop_records_transcripts_to_journal(tmp_path: Path) -> None:
    journal = FakeTranscriptLog()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["abrí firefox"]),
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        transcript_log=journal,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert journal.records == [("abrí firefox", "open_app", "execute")]


def test_loop_off_state_never_consults_wake_or_capture(tmp_path: Path) -> None:
    wake = FakeWake([True])
    capture = FakeCapture(["abrí firefox"])
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=capture,
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        switch_state=lambda: True,
    )
    outcome = run(pipeline, iterations=3)
    assert outcome == "off"
    assert len(wake.results) == 1
    assert len(capture.transcripts) == 1


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


# --- Verify fixes: spoken ack before long-running ops (voice-pipeline) --------
def test_long_llm_operation_speaks_ack_before_executing(tmp_path: Path) -> None:
    speaker = FakeSpeaker()
    executor = TrackingExecutor(
        speaker,
        ActionResult(ok=True, spoken="listo, implementé el login"),
        long_running={"implement"},
    )
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["implementá el login"]),
        interpreter=FakeInterpreter([_interp(_intent(intent="implement", entities={"text": "login"}))]),
        speaker=speaker,
        executor=executor,
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert executor.spoken_before_execute == [LONG_OPERATION_ACK]
    assert speaker.said == [LONG_OPERATION_ACK, "listo, implementé el login"]


def test_short_operation_speaks_no_ack(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["abrí firefox"],
        interpreter_script=[_interp(_intent())],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert pipeline.speaker.said == ["ok"]


def test_create_doc_invalid_path_degrades_to_spoken_error(tmp_path: Path) -> None:
    blocker = tmp_path / "blocker"
    blocker.write_text("soy un archivo, no una carpeta")
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["creá una nota"]),
        interpreter=FakeInterpreter([_interp(_intent(intent="create_doc", entities={"text": "nota"}))]),
        speaker=FakeSpeaker(),
        executor=_build_registry(),
        session=Session(active_project=str(blocker)),
        cwd=str(tmp_path),
        git_runner=lambda cwd: None,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "failed"
    assert "no pude crear" in pipeline.speaker.said[-1]


# --- PR4: open_repo owns project switching; registry wired into the loop -----
class _FakeOpenCodeManager:
    def ensure_server(self, port, repo):
        self.calls = getattr(self, "calls", [])
        self.calls.append((port, repo))
        return True


def test_open_repo_with_explicit_repo_executes_without_active_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manager = _FakeOpenCodeManager()
    monkeypatch.setattr("jarvis.actions.opencode.ServerManager", lambda *a, **k: manager)
    session = Session()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["abrí " + str(tmp_path)], clock=FakeClock(), advance=16.0),
        interpreter=FakeInterpreter(
            [_interp(_intent(intent="open_repo", entities={"repo": str(tmp_path)}))]
        ),
        speaker=FakeSpeaker(),
        executor=_build_registry(),
        session=session,
        cwd=str(tmp_path),
        git_runner=lambda cwd: None,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert session.active_project == str(tmp_path)
    assert manager.calls == [(32111, Path(str(tmp_path)))]


def test_loop_dispatches_open_app_through_real_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    commands = []
    monkeypatch.setattr(
        "jarvis.actions.base.safe_run",
        lambda command, timeout=20.0: commands.append(command) or (0, ""),
    )
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["abrí firefox"], clock=FakeClock(), advance=16.0),
        interpreter=FakeInterpreter([_interp(_intent(entities={"app": "firefox"}))]),
        speaker=FakeSpeaker(),
        executor=_build_registry(),
        session=Session(),
        cwd=str(tmp_path),
        git_runner=lambda cwd: None,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert commands == [["xdg-open", "firefox"]]


def _build_registry():
    from jarvis.actions.base import build_registry

    return build_registry()
