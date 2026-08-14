"""PR6 bootstrap: build_pipeline() assembles the real voice pipeline (task 5.7).

Design (openspec PR6): ``loop.start()`` must run the orchestrator with the
REAL adapters — sounddevice mic, OpenWakeWord, whisper-cli, piper, paplay,
the opencode executor registry. The factory takes injected adapters for tests;
construction defaults are verified by recording the constructor calls so no
hardware/model is touched in unit tests.
"""

from __future__ import annotations

import pytest

from jarvis import config
from jarvis.orchestrator import loop
from jarvis.orchestrator.session import Session


def _recording(monkeypatch: pytest.MonkeyPatch) -> dict[str, dict]:
    calls: dict[str, dict] = {}

    for name in (
        "SoundDeviceCapturer",
        "OpenWakeWord",
        "WhisperSTT",
        "PiperTTS",
        "Playback",
    ):

        def _make(n: str):
            class Recorder:
                def __init__(self, *args, **kwargs) -> None:
                    calls[n] = {"args": args, "kwargs": kwargs}

            Recorder.__name__ = n
            return Recorder

        monkeypatch.setattr(loop, name, _make(name), raising=False)
    monkeypatch.setattr(loop, "UtteranceCapture", lambda *a, **k: "capture")
    monkeypatch.setattr(loop, "PiperSpeaker", lambda *a, **k: "speaker")
    monkeypatch.setattr(loop, "MicSwitch", lambda *a, **k: (lambda: False))
    monkeypatch.setattr(loop, "build_registry", lambda: "executor")
    return calls


def test_build_pipeline_wires_real_adapters_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _recording(monkeypatch)

    pipeline = loop.build_pipeline(Session(), cwd="/tmp")

    assert pipeline.capture == "capture"
    assert pipeline.speaker == "speaker"
    assert pipeline.executor == "executor"
    assert pipeline.switch_state is not None
    assert calls["SoundDeviceCapturer"]["kwargs"]["sample_rate"] == config.AUDIO_SAMPLE_RATE
    assert calls["OpenWakeWord"]["kwargs"]["threshold"] == config.WAKE_THRESHOLD
    stt = calls["WhisperSTT"]["kwargs"]
    assert stt["whisper_cli"] == config.WHISPER_CLI
    assert stt["model_small"] == config.WHISPER_MODEL
    assert stt["beam"] == config.WHISPER_BEAM
    assert stt["vad_model"] == config.WHISPER_VAD_MODEL
    assert stt["gate_duration_s"] == config.STT_GATE_DURATION_S
    assert calls["PiperTTS"]["kwargs"]["piper_bin"] == config.PIPER_BIN
    assert calls["PiperTTS"]["kwargs"]["model"] == config.PIPER_MODEL
    assert calls["Playback"]["kwargs"]["player"] == config.PLAYER_BIN
    assert pipeline.cwd == "/tmp"


def test_build_pipeline_omits_medium_model_when_not_promoted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "STT_MEDIUM_PROMOTED", False)
    calls = _recording(monkeypatch)

    loop.build_pipeline(Session(), cwd="/tmp")

    assert calls["WhisperSTT"]["kwargs"]["model_medium"] is None


def test_build_pipeline_injects_fakes_and_runs_end_to_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from collections import deque

    from jarvis.audio.pipeline import PiperSpeaker
    from jarvis.orchestrator.contracts import ActionResult
    from jarvis.orchestrator.session import load_state

    class _FakeClock:
        def now(self) -> float:
            return 0.0

    class _FakeWake:
        def __init__(self) -> None:
            self.results = deque([True])
            self.calls = 0

        def wait(self, timeout: float) -> bool:
            self.calls += 1
            return self.results.popleft() if self.results else False

    class _FakeInterp:
        def __call__(self, text: str):
            from jarvis.interpreter import Interpretation
            from jarvis.interpreter.schema import Intent

            return Interpretation(
                intent=Intent(
                    intent="open_app", entities={"app": "firefox"}, confidence=0.9
                ),
                needs_reask=False,
                unsupported=False,
            )

    class _FakeExecutor:
        def execute(self, intent, session) -> ActionResult:
            return ActionResult(ok=True, spoken="ok")

    class _FakeTTS:
        def synthesize(self, text, out_path):
            import pathlib

            p = pathlib.Path(out_path)
            p.write_bytes(b"RIFF")
            return p

    class _FakePlayback:
        def play(self, wav_path) -> None:
            pass

    class _FakeCapture:
        def capture(self) -> str:
            return "abrí firefox"

    wake = _FakeWake()
    capture = _FakeCapture()
    speaker = PiperSpeaker(_FakeTTS(), _FakePlayback())
    pipeline = loop.build_pipeline(
        load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        wake=wake,
        capture=capture,
        speaker=speaker,
        interpreter=_FakeInterp(),
        executor=_FakeExecutor(),
        switch_state=lambda: False,
    )

    from jarvis.orchestrator.loop import run

    outcome = run(pipeline, iterations=3)

    assert outcome == "executed"
    assert wake.calls == 1
