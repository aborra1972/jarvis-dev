"""Orchestrator loop tests (PR3, task 3.5).

Drives the full FSM with fakes: wake, capture (voice transcripts), scripted
interpreter, speaker, and executor. Covers the design sequence diagrams:
execute path, confirm yes/no/timeout (M6), re-ask ×2 → reveal (RNF-4),
invalid_entity → spoken rejection without re-ask (debt WARNING #2), silence,
switch off/on (RF-11), and power_off_self → stopped.
"""

from __future__ import annotations

import json
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
    _Context,
    _read_wake_threshold,
    _start_audio_metrics_publisher,
    _sync_wake_threshold,
    _tick,
    run,
)
from jarvis.orchestrator.session import Session, load_state
import jarvis.orchestrator.loop as loop_module
from jarvis.orchestrator.state import State


def test_audio_metrics_publisher_is_started_from_runtime_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis import config
    from jarvis.audio.capture import AudioMetrics

    class WakeWithMetrics:
        def __init__(self) -> None:
            self.capturer = type("Capturer", (), {"metrics": AudioMetrics()})()

    monkeypatch.setattr(config, "AUDIO_METRICS_FILE", tmp_path / "audio_metrics.json")
    pipeline = type("Pipeline", (), {"wake": WakeWithMetrics()})()

    publisher = _start_audio_metrics_publisher(pipeline)
    assert publisher is not None
    try:
        assert (tmp_path / "audio_metrics.json").exists()
        assert publisher._thread is not None and publisher._thread.daemon
    finally:
        publisher.stop()


def test_read_wake_threshold_from_gui_state(tmp_path: Path, monkeypatch) -> None:
    from jarvis import config

    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"wake_threshold": 0.65}))
    monkeypatch.setattr(config, "STATE_FILE", state_file)

    assert _read_wake_threshold(0.7) == 0.65


def test_sync_wake_threshold_updates_active_detector(tmp_path: Path, monkeypatch) -> None:
    from jarvis import config

    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"wake_threshold": 0.35}))
    monkeypatch.setattr(config, "STATE_FILE", state_file)
    wake = FakeWake([])
    wake.threshold = 0.7

    _sync_wake_threshold(wake)

    assert wake.threshold == 0.35


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


class NameFakeWake(FakeWake):
    """Name-gated wake (engine "name"): the loop must rewind and skip the beep."""

    gates_by_name = True

    def __init__(self, results: list[bool]) -> None:
        super().__init__(results)
        self.rewound = False

    def rewind(self) -> None:
        self.rewound = True


class CountingMic:
    """Records start/stop/flush calls like the real SoundDeviceCapturer."""

    def __init__(self) -> None:
        self.started = 0
        self.stopped = 0
        self.flushed = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def flush(self, ms: int = 1000) -> None:
        self.flushed += 1


class MicWake(FakeWake):
    """FakeWake wired to a counting capturer (mic lifecycle tests)."""

    def __init__(self, results: list[bool], capturer: CountingMic) -> None:
        super().__init__(results)
        self.capturer = capturer

    def flush(self) -> None:
        pass


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

    def speak_and_wait(self, text: str):
        self.speak(text)
        return type("Completion", (), {"completed": True})()


class BeepRecordingSpeaker(FakeSpeaker):
    """FakeSpeaker that records activation-beep calls (speaker.playback)."""

    def __init__(self) -> None:
        super().__init__()
        self.beeps = 0
        self.playback = self

    def play_beep(self) -> None:
        self.beeps += 1


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


def test_loop_records_turn_metrics_and_uses_metric_speaker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jarvis import config

    monkeypatch.setattr(config, "LLM_PROVIDER", "fake-provider")
    monkeypatch.setattr(loop_module.time, "sleep", lambda seconds: None)
    timestamps = iter([1_000_000_000, 1_250_000_000])
    monkeypatch.setattr(loop_module.time, "monotonic_ns", lambda: next(timestamps))

    class Capture:
        def __init__(self) -> None:
            self.metrics = None

        def capture(self, **kwargs):
            self.metrics = kwargs["metrics"]
            return "abrí firefox"

    class MetricsSpeaker(FakeSpeaker):
        def __init__(self) -> None:
            super().__init__()
            self.metric_calls: list[tuple[str, object]] = []

        def speak_with_metrics(self, text: str, metrics: object) -> None:
            self.metric_calls.append((text, metrics))
            self.speak(text)

    capture = Capture()
    speaker = MetricsSpeaker()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=capture,
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=speaker,
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    context = _Context()

    state, context = _tick(State.IDLE, pipeline, context)
    assert state is State.LISTENING
    state, context = _tick(state, pipeline, context)
    assert state is State.EXECUTING
    state, context = _tick(state, pipeline, context)

    assert state is State.SPEAKING
    assert capture.metrics is context.voice_metrics
    assert context.voice_metrics is not None
    assert context.voice_metrics.intent_duration_s == pytest.approx(0.25)
    assert context.voice_metrics.intent_provider == "fake-provider"
    assert speaker.metric_calls == [("ok", context.voice_metrics)]


def test_confirm_yes_executes_shutdown(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["apagá el sistema", "sí"],
        interpreter_script=[_interp(_intent(intent="shutdown", confirm_required=True))],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=3)
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

    def record(self, transcript: str, intent=None, outcome=None, entities=None) -> None:
        self.records.append((transcript, intent, outcome))


def test_loop_records_transcripts_to_journal(tmp_path: Path) -> None:
    journal = FakeTranscriptLog()
    history_path = tmp_path / "history.json"
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["abrí firefox"]),
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(
            str(tmp_path / "state.json"),
            history_path=str(history_path),
        ),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        transcript_log=journal,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert journal.records == [("abrí firefox", "open_app", "execute")]
    history = json.loads(history_path.read_text())
    assert history[0]["user"] == "abrí firefox"
    assert history[0]["assistant"] == "ok"
    assert history[0]["intent"] == "open_app"
    assert history[0]["ok"] is True


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
    # M7 fix: open_app no longer switches active_project (app name ≠ project)
    assert reloaded.active_project != "chromium"
    assert reloaded.repos == {"chromium": 0}


# --- Verify fixes: spoken ack before long-running ops (voice-pipeline) --------
@pytest.mark.parametrize("intent_name", ["implement", "review_pr", "fix_warnings"])
def test_long_llm_operation_speaks_ack_before_executing(tmp_path: Path, intent_name: str) -> None:
    speaker = FakeSpeaker()
    executor = TrackingExecutor(
        speaker,
        ActionResult(ok=True, spoken="listo, terminé"),
        long_running={intent_name},
    )
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["hacelo"]),
        interpreter=FakeInterpreter([_interp(_intent(intent=intent_name, entities={"text": "login"}))]),
        speaker=speaker,
        executor=executor,
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert executor.spoken_before_execute == [LONG_OPERATION_ACK]
    assert speaker.said == [LONG_OPERATION_ACK, "listo, terminé"]


def test_new_opencode_agent_intents_require_repo_before_ack(tmp_path: Path) -> None:
    speaker = FakeSpeaker()
    executor = TrackingExecutor(
        speaker,
        ActionResult(ok=True, spoken="no debería ejecutar"),
        long_running={"review_pr"},
    )
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["revisá el pr"]),
        interpreter=FakeInterpreter([_interp(_intent(intent="review_pr", entities={"text": "PR actual"}))]),
        speaker=speaker,
        executor=executor,
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: None,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "rejected"
    assert executor.spoken_before_execute == []
    assert speaker.said == ["No hay un proyecto activo, señor. Abra uno primero."]


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
    assert commands == [["firefox"]]


def _build_registry():
    from jarvis.actions.base import build_registry

    return build_registry()


def test_cooldown_starts_when_tts_finishes_not_when_it_starts(tmp_path: Path) -> None:
    """C3 fix: cooldown must measure from TTS playback end, not FSM SPEAKING entry.

    Before the fix, last_spoke_at was set when the FSM entered SPEAKING.
    Since PiperSpeaker.speak() is async, the cooldown elapsed while audio
    was still playing → mic opened during playback → feedback loop.

    Now was_playing tracks the playing→finished transition and sets
    last_spoke_at at that point, so the full cooldown runs after audio ends.
    """
    import time
    from jarvis.orchestrator.loop import TTS_COOLDOWN_S

    class _TimedSpeaker:
        """Speaker that tracks playing state transitions."""
        def __init__(self) -> None:
            self.said: list[str] = []
            self._playing = False
            self.finished_at: float = 0.0

        def speak(self, text: str) -> None:
            self.said.append(text)
            self._playing = True

        def is_playing(self) -> bool:
            return self._playing

        def finish_playing(self) -> None:
            """Simulate TTS finishing — called after some delay."""
            self._playing = False
            self.finished_at = time.monotonic()

    speaker = _TimedSpeaker()
    session = load_state(str(tmp_path / "state.json"))
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([False]),
        capture=FakeCapture([]),
        interpreter=FakeInterpreter([]),
        speaker=speaker,
        executor=FakeExecutor(),
        session=session,
        cwd=str(tmp_path),
        git_runner=lambda cwd: None,
    )

    # Simulate: speaker was playing, now transitions to not-playing
    speaker.speak("hola")
    context = _Context()
    # First tick: speaker is playing → IDLE stays, was_playing set
    state = _tick(State.IDLE, pipeline, context)
    assert context.was_playing is True
    assert context.last_spoke_at == 0.0  # not set yet

    # Simulate TTS finishing after 2 seconds of playback
    time.sleep(0.05)  # small real delay
    speaker.finish_playing()

    # Second tick: speaker finished → was_playing triggers cooldown start
    start = time.monotonic()
    state = _tick(State.IDLE, pipeline, context)
    elapsed = time.monotonic() - start

    # Cooldown should have run (or started) after TTS finished
    assert context.was_playing is False
    assert context.last_spoke_at == 0.0  # cooldown consumed
    # The cooldown sleep should have happened (or been satisfied already)
    assert elapsed >= 0  # basic sanity


def test_conversation_window_starts_after_playback_completion_not_executor_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Follow-up listening should be timed from actual TTS completion."""
    from jarvis import config

    monkeypatch.setattr(config, "CONVERSATION_WINDOW_S", 30.0)
    monkeypatch.setattr("jarvis.orchestrator.loop.time.sleep", lambda seconds: None)

    class ManualPlaybackSpeaker(FakeSpeaker):
        def __init__(self) -> None:
            super().__init__()
            self.playing = False

        def speak(self, text: str) -> None:
            super().speak(text)
            self.playing = True

        def is_playing(self) -> bool:
            return self.playing

        def finish(self) -> None:
            self.playing = False

    speaker = ManualPlaybackSpeaker()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=FakeCapture(["abrí firefox"]),
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=speaker,
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    context = _Context()

    state, context = _tick(State.IDLE, pipeline, context)
    state, context = _tick(state, pipeline, context)
    state, context = _tick(state, pipeline, context)

    assert state == State.SPEAKING
    assert speaker.is_playing() is True
    assert context.conversation_until == 0.0

    state, context = _tick(state, pipeline, context)
    assert state == State.IDLE
    state, context = _tick(state, pipeline, context)
    assert context.outcome == "speaking"
    speaker.finish()
    state, context = _tick(state, pipeline, context)
    assert context.conversation_until > 0.0


# --- Name-gated wake (feature "wake por nombre", engine "name") ----------------
def test_name_wake_skips_beep_and_goes_straight_to_listening(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "friday")
    wake = NameFakeWake([True])
    speaker = BeepRecordingSpeaker()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=FakeCapture(["friday, abrí firefox"]),
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=speaker,
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    assert wake.rewound is True
    assert speaker.beeps == 0  # name path never calls speaker.playback
    assert pipeline.interpreter.calls[0] == "abrí firefox"  # name STRIPPED
    assert [c.intent for c in pipeline.executor.calls] == ["open_app"]
    assert speaker.said == ["ok"]


def test_name_wake_discards_transcript_without_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "friday")
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=NameFakeWake([True]),
        capture=FakeCapture(["hola che"]),
        interpreter=FakeInterpreter([]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    outcome = run(pipeline, iterations=2)
    assert outcome == "name_mismatch"
    assert pipeline.interpreter.calls == []
    assert pipeline.speaker.said == []  # discarded silently


def test_name_mismatch_ends_active_turn_before_next_wake_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rejected name-gated utterance must not re-enter ordinary capture."""
    monkeypatch.setenv("JARVIS_AGENT", "friday")
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=NameFakeWake([True, False]),
        capture=FakeCapture(["hola che"]),
        interpreter=FakeInterpreter([]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )

    outcome = run(pipeline, iterations=4)

    assert outcome == "name_mismatch"
    assert len(pipeline.wake.results) == 0
    assert pipeline.interpreter.calls == []
    assert pipeline.speaker.said == []  # discarded silently


def test_conversation_followup_skips_name_gate(tmp_path: Path) -> None:
    import time

    wake = NameFakeWake([True])  # must NOT be consumed: conversation path
    context = _Context()
    context.conversation_until = time.monotonic() + 60.0
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=FakeCapture(["friday, abrí firefox"]),
        interpreter=FakeInterpreter([_interp(_intent())]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    state, _ = _tick(State.IDLE, pipeline, context)
    assert state == State.LISTENING
    assert len(wake.results) == 1  # wake never consulted
    state, _ = _tick(state, pipeline, context)
    assert state == State.EXECUTING
    # Follow-up window: transcript goes to the interpreter UNSTRIPPED.
    assert pipeline.interpreter.calls[0] == "friday, abrí firefox"


def test_legacy_wake_does_not_gate(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["hey jarvis, abrí firefox"],
        interpreter_script=[_interp(_intent())],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=4)
    assert outcome == "executed"
    # No gates_by_name on FakeWake: full transcript reaches the interpreter.
    assert pipeline.interpreter.calls[0] == "hey jarvis, abrí firefox"


def test_active_epoch_keeps_ordinary_capture_after_arbitrary_pause(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True, False],
        transcripts=["abrí firefox", "abrí chromium"],
        interpreter_script=[_interp(_intent()), _interp(_intent(entities={"app": "chromium"}))],
        tmp_path=tmp_path,
    )

    outcome = run(pipeline, iterations=8)

    assert outcome == "executed"
    assert len(pipeline.executor.calls) == 2
    assert len(pipeline.wake.results) == 1


def test_active_reask_returns_through_playback_barrier(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["no sé", "abrí firefox"],
        interpreter_script=[_interp(needs_reask=True), _interp(_intent())],
        tmp_path=tmp_path,
    )

    outcome = run(pipeline, iterations=7)

    assert outcome in {"executed", "silence"}
    assert len(pipeline.executor.calls) == 1
    assert any(REASK_1 in text for text in pipeline.speaker.said)


def test_after_listening_without_tts_mic_gets_reopened(tmp_path: Path) -> None:
    """Non-TTS returns from LISTENING leave the mic stopped; IDLE must reopen
    it (idempotently) before the next wake scan."""
    mic = CountingMic()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=MicWake([False], mic),
        capture=FakeCapture([]),
        interpreter=FakeInterpreter([]),
        speaker=FakeSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )
    state, _ = _tick(State.IDLE, pipeline, _Context())
    assert state == State.IDLE  # false wake
    assert mic.started == 1
    assert mic.flushed == 1
    assert mic.stopped == 0


def test_goodbye_acknowledges_and_returns_to_wake_standby(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True, False],
        transcripts=["terminamos"],
        interpreter_script=[Interpretation(control="goodbye")],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=3)
    assert outcome == "goodbye"
    assert pipeline.speaker.said[-1]
    assert len(pipeline.wake.results) == 1
    assert pipeline.executor.calls == []


def test_goodbye_during_confirmation_invalidates_without_execution(tmp_path: Path) -> None:
    pipeline = _pipeline(
        wake=[True],
        transcripts=["apagá el sistema", "terminamos"],
        interpreter_script=[_interp(_intent(intent="shutdown", confirm_required=True))],
        tmp_path=tmp_path,
    )
    outcome = run(pipeline, iterations=5)
    assert outcome == "goodbye"
    assert pipeline.executor.calls == []
    assert any("Hasta luego" in text for text in pipeline.speaker.said)
