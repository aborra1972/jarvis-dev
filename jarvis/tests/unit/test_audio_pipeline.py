"""Voice wiring tests (PR5, item 6: wiring + item 7: switch).

The orchestrator loop (PR3) consumes contracts.Capture / WakeDetector /
Speaker. PR5 wires real audio adapters over them: UtteranceCapture
(capturer + VAD + STT), PiperSpeaker (TTS + playback), and MicSwitch (RF-11:
off releases the mic, wake is not consulted). These tests drive the adapters
with fakes — the real hardware swap is E2E (PR6).
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
import pytest

from jarvis.audio.capture import BLOCK_MS, SAMPLE_RATE, SilenceVAD
from jarvis.audio.playback import PlaybackError
from jarvis.audio.pipeline import MicSwitch, PiperSpeaker, UtteranceCapture
from jarvis.audio.stt import STTError
from jarvis.audio.tts import TTSError
from jarvis.interpreter import Interpretation
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult
from jarvis.orchestrator.loop import Pipeline, run
from jarvis.orchestrator.session import load_state

BLOCK = SAMPLE_RATE * BLOCK_MS // 1000


def _speech(freq: int = 440) -> np.ndarray:
    return (0.4 * np.sin(2 * np.pi * freq * np.arange(BLOCK) / SAMPLE_RATE)).astype(
        np.float32
    )


def _silence() -> np.ndarray:
    return np.zeros(BLOCK, dtype=np.float32)


class FakeCapturer:
    def __init__(self, blocks: list[np.ndarray]) -> None:
        self._queue = deque(blocks)
        self.reads = 0
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        self.reads += 1
        return self._queue.popleft() if self._queue else None


class FakeSTT:
    def __init__(self, transcript: str, error: bool = False) -> None:
        self.transcript = transcript
        self.error = error
        self.calls: list[tuple[Path, float]] = []

    def transcribe(self, wav_path: Path, duration_s: float) -> str:
        self.calls.append((Path(wav_path), duration_s))
        if self.error:
            raise STTError("boom")
        return self.transcript


class FakeTTS:
    def __init__(self, error: bool = False) -> None:
        self.error = error
        self.texts: list[str] = []
        self.outs: list[Path] = []

    def synthesize(self, text: str, out_path: Path) -> Path:
        self.texts.append(text)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"RIFF")
        self.outs.append(out)
        if self.error:
            raise TTSError("boom")
        return out


class FakePlayback:
    def __init__(self, error: bool = False) -> None:
        self.error = error
        self.played: list[Path] = []

    def play(self, wav_path: Path) -> None:
        if self.error:
            raise PlaybackError("boom")
        self.played.append(Path(wav_path))


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
        self.calls = 0

    def wait(self, timeout: float) -> bool:
        self.calls += 1
        return self.results.popleft() if self.results else False


class FakeInterpreter:
    def __init__(self, script: list[Interpretation]) -> None:
        self.script = deque(script)

    def __call__(self, text: str) -> Interpretation:
        return self.script.popleft() if self.script else Interpretation()


class FakeExecutor:
    def __init__(self) -> None:
        self.calls: list[Intent] = []

    def execute(self, intent: Intent, session: object) -> ActionResult:
        self.calls.append(intent)
        return ActionResult(ok=True, spoken="ok")


def _vad() -> SilenceVAD:
    return SilenceVAD(threshold=0.02, silence_s=0.1, max_s=3.0)


# --- UtteranceCapture (contracts.Capture) ------------------------------------
def test_utterance_capture_returns_transcript(tmp_path: Path) -> None:
    capturer = FakeCapturer([_speech(), _speech(), _speech(), _silence()])
    stt = FakeSTT("abrí firefox")
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    assert capture.capture() == "abrí firefox"
    assert len(stt.calls) == 1
    wav, duration = stt.calls[0]
    assert wav.is_file()
    assert duration == pytest.approx(0.4)


def test_utterance_capture_returns_none_on_pure_silence(tmp_path: Path) -> None:
    capturer = FakeCapturer([_silence(), _silence(), _silence()])
    stt = FakeSTT("abrí firefox")
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    assert capture.capture() is None
    assert stt.calls == []


def test_utterance_capture_returns_none_when_no_frames(tmp_path: Path) -> None:
    capture = UtteranceCapture(FakeCapturer([]), FakeSTT("x"), _vad(), wav_dir=tmp_path)
    assert capture.capture() is None


def test_utterance_capture_returns_none_on_stt_error(tmp_path: Path) -> None:
    capturer = FakeCapturer([_speech(), _silence()])
    stt = FakeSTT("", error=True)
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    assert capture.capture() is None  # silence-like recovery, loop stays idle


# --- PiperSpeaker (contracts.Speaker) -----------------------------------------
def test_piper_speaker_speaks_through_tts_and_playback(tmp_path: Path) -> None:
    tts = FakeTTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("hecho")

    assert tts.texts == ["hecho"]
    assert playback.played == tts.outs
    assert tts.outs[0].is_file()


def test_piper_speaker_survives_tts_failure(tmp_path: Path) -> None:
    speaker = PiperSpeaker(FakeTTS(error=True), FakePlayback(), out_dir=tmp_path)
    speaker.speak("hecho")  # must not raise


def test_piper_speaker_survives_playback_failure(tmp_path: Path) -> None:
    speaker = PiperSpeaker(FakeTTS(), FakePlayback(error=True), out_dir=tmp_path)
    speaker.speak("hecho")  # must not raise


# --- MicSwitch (RF-11: off releases the mic) ----------------------------------
def test_mic_switch_releases_mic_when_off_and_resumes_on() -> None:
    state = {"off": False}
    capturer = FakeCapturer([_speech()])

    def switch_state() -> bool:
        return state["off"]

    switch = MicSwitch(capturer, switch_state)
    assert capturer.started == 1
    assert capturer.stopped == 0
    assert switch() is False

    state["off"] = True
    assert switch() is True
    assert capturer.stopped == 1

    state["off"] = False
    assert switch() is False
    assert capturer.started == 2


# --- Loop wiring (item 6) -----------------------------------------------------
def _intent() -> Intent:
    return Intent(
        intent="open_app",
        entities={"app": "firefox"},
        confidence=0.9,
        confirm_required=False,
    )


def _interp() -> Interpretation:
    return Interpretation(intent=_intent(), needs_reask=False, unsupported=False)


def test_loop_listening_uses_capturer_wake_and_stt(
    tmp_path: Path,
) -> None:
    capturer = FakeCapturer([_speech(), _speech(), _speech(), _silence()])
    stt = FakeSTT("abrí firefox")
    tts = FakeTTS()
    playback = FakePlayback()
    wake = FakeWake([True])

    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path),
        interpreter=FakeInterpreter([_interp()]),
        speaker=PiperSpeaker(tts, playback, out_dir=tmp_path),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        switch_state=MicSwitch(capturer, lambda: False),
    )

    outcome = run(pipeline, iterations=4)

    assert outcome == "executed"
    assert wake.calls == 1
    assert len(stt.calls) == 1  # listening transcribes one captured utterance
    assert tts.texts == ["ok"]  # speaking goes through TTS + playback
    assert playback.played == tts.outs
    assert capturer.reads > 0


def test_loop_off_releases_mic_and_never_consults_wake(
    tmp_path: Path,
) -> None:
    state = {"off": True}
    capturer = FakeCapturer([_speech()])
    wake = FakeWake([True])  # would trigger if consulted

    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=UtteranceCapture(capturer, FakeSTT("x"), _vad(), wav_dir=tmp_path),
        interpreter=FakeInterpreter([]),
        speaker=PiperSpeaker(FakeTTS(), FakePlayback(), out_dir=tmp_path),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        switch_state=MicSwitch(capturer, lambda: state["off"]),
    )

    outcome = run(pipeline, iterations=1)
    assert outcome == "switched_off"
    assert wake.calls == 0
    assert capturer.reads == 0
    assert capturer.stopped == 1

    state["off"] = False
    outcome = run(pipeline, iterations=1)
    assert outcome in ("woke", "no_wake")
    assert wake.calls == 1
    assert capturer.started >= 1
