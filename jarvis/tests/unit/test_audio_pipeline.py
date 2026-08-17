"""Voice wiring tests (PR5, item 6: wiring + item 7: switch).

The orchestrator loop (PR3) consumes contracts.Capture / WakeDetector /
Speaker. PR5 wires real audio adapters over them: UtteranceCapture
(capturer + VAD + STT), PiperSpeaker (TTS + playback), and MicSwitch (RF-11:
off releases the mic, wake is not consulted). These tests drive the adapters
with fakes — the real hardware swap is E2E (PR6).
"""

from __future__ import annotations

import threading
import time
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
from jarvis.orchestrator.contracts import ActionResult, CaptureError
from jarvis.orchestrator.loop import STT_ERROR_SPOKEN, Pipeline, run
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


class Mp3TTS(FakeTTS):
    """EdgeTTS-shaped fake: output extension is .mp3 (drives the speaker)."""

    extension = ".mp3"

    def synthesize(self, text: str, out_path: Path) -> Path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"MP3")
        self.texts.append(text)
        self.outs.append(out)
        return out


class _SlowTTS:
    """TTS that signals when synthesis starts and blocks until released."""

    def __init__(self, started: threading.Event) -> None:
        self.started = started
        self.texts: list[str] = []

    def synthesize(self, text: str, out_path: Path) -> Path:
        self.started.set()
        time.sleep(0.2)
        self.texts.append(text)
        Path(out_path).write_bytes(b"RIFF")
        return Path(out_path)


class _FlakyTTS:
    """TTS that fails exactly once, then succeeds."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.outs: list[Path] = []
        self.fail_next = True

    def synthesize(self, text: str, out_path: Path) -> Path:
        if self.fail_next:
            self.fail_next = False
            raise TTSError("boom")
        self.texts.append(text)
        out = Path(out_path)
        out.write_bytes(b"RIFF")
        self.outs.append(out)
        return out


class _StuckSpeaker:
    """Speaker that never finishes playing (for the IDLE drop-wake gate)."""

    spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)

    def is_playing(self) -> bool:
        return True


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
    assert wav.suffix == ".wav"
    assert duration == pytest.approx(0.4)


def test_utterance_capture_cleans_wav_after_transcription(tmp_path: Path) -> None:
    """Capture WAV files must be deleted after STT to avoid disk fill."""
    capturer = FakeCapturer([_speech(), _silence()])
    stt = FakeSTT("hola")
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    capture.capture()
    wav_files = list(tmp_path.glob("jarvis-capture-*.wav"))
    assert wav_files == [], f"WAVs should be cleaned up, found: {wav_files}"


def test_utterance_capture_cleans_wav_on_stt_error(tmp_path: Path) -> None:
    """Capture WAV must be cleaned even when STT raises."""
    capturer = FakeCapturer([_speech(), _silence()])
    stt = FakeSTT("", error=True)
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    with pytest.raises(CaptureError):
        capture.capture()
    wav_files = list(tmp_path.glob("jarvis-capture-*.wav"))
    assert wav_files == [], f"WAVs should be cleaned on error, found: {wav_files}"


def test_utterance_capture_returns_none_on_pure_silence(tmp_path: Path) -> None:
    capturer = FakeCapturer([_silence(), _silence(), _silence()])
    stt = FakeSTT("abrí firefox")
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    assert capture.capture() is None
    assert stt.calls == []


def test_utterance_capture_returns_none_when_no_frames(tmp_path: Path) -> None:
    capture = UtteranceCapture(FakeCapturer([]), FakeSTT("x"), _vad(), wav_dir=tmp_path)
    assert capture.capture() is None


def test_utterance_capture_raises_on_stt_error(tmp_path: Path) -> None:
    # PR6 (item 5): an STT failure must surface so the loop replies with a
    # spoken error instead of pretending nothing was heard.
    capturer = FakeCapturer([_speech(), _silence()])
    stt = FakeSTT("", error=True)
    capture = UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path)

    with pytest.raises(CaptureError):
        capture.capture()


# --- PiperSpeaker (contracts.Speaker, PR6 async queue) -------------------------
def test_piper_speaker_speaks_through_tts_and_playback(tmp_path: Path) -> None:
    tts = FakeTTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("hecho")
    speaker.flush()

    assert tts.texts == ["hecho"]
    assert playback.played == tts.outs


def test_piper_speaker_cleans_media_after_playback(tmp_path: Path) -> None:
    """TTS media files must be deleted after playback to avoid disk fill."""
    tts = FakeTTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("hecho")
    speaker.flush()

    media_files = list(tmp_path.glob("jarvis-reply-*"))
    assert media_files == [], f"Media files should be cleaned up, found: {media_files}"


def test_piper_speaker_cleans_media_on_tts_error(tmp_path: Path) -> None:
    """TTS media must be cleaned even when TTS fails."""
    speaker = PiperSpeaker(FakeTTS(error=True), FakePlayback(), out_dir=tmp_path)
    speaker.speak("falla")
    speaker.flush()

    media_files = list(tmp_path.glob("jarvis-reply-*"))
    assert media_files == [], f"Media files should be cleaned on error, found: {media_files}"


def test_piper_speaker_cleans_media_on_playback_error(tmp_path: Path) -> None:
    """TTS media must be cleaned even when playback fails."""
    speaker = PiperSpeaker(FakeTTS(), FakePlayback(error=True), out_dir=tmp_path)
    speaker.speak("falla")
    speaker.flush()

    media_files = list(tmp_path.glob("jarvis-reply-*"))
    assert media_files == [], f"Media files should be cleaned on error, found: {media_files}"


def test_piper_speaker_writes_mp3_when_tts_extension_is_mp3(tmp_path: Path) -> None:
    tts = Mp3TTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("hecho")
    speaker.flush()

    assert tts.outs[0].suffix == ".mp3"
    assert playback.played == tts.outs


def test_piper_speaker_preserves_order_and_delivers_all(tmp_path: Path) -> None:
    tts = FakeTTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("uno")
    speaker.speak("dos")
    speaker.speak("tres")
    speaker.flush()

    assert tts.texts == ["uno", "dos", "tres"]
    assert playback.played == tts.outs


def test_piper_speaker_survives_tts_failure(tmp_path: Path) -> None:
    speaker = PiperSpeaker(FakeTTS(error=True), FakePlayback(), out_dir=tmp_path)
    speaker.speak("hecho")  # must not raise
    speaker.flush()


def test_piper_speaker_survives_playback_failure(tmp_path: Path) -> None:
    speaker = PiperSpeaker(FakeTTS(), FakePlayback(error=True), out_dir=tmp_path)
    speaker.speak("hecho")  # must not raise
    speaker.flush()


def test_piper_speaker_is_playing_reports_true_until_drained(tmp_path: Path) -> None:
    started = threading.Event()
    tts = _SlowTTS(started)
    speaker = PiperSpeaker(tts, FakePlayback(), out_dir=tmp_path)

    assert speaker.is_playing() is False
    speaker.speak("hola")
    assert started.wait(timeout=2), "worker must start synthesizing"
    assert speaker.is_playing() is True

    speaker.flush()
    assert speaker.is_playing() is False
    assert tts.texts == ["hola"]


def test_piper_speaker_worker_survives_error_and_continues(tmp_path: Path) -> None:
    tts = _FlakyTTS()
    playback = FakePlayback()
    speaker = PiperSpeaker(tts, playback, out_dir=tmp_path)

    speaker.speak("falla")
    speaker.speak("sigue")
    speaker.flush()

    assert tts.texts == ["sigue"]
    assert playback.played == tts.outs
    assert speaker.is_playing() is False


def test_piper_speaker_close_stops_worker_and_speak_after_is_safe(tmp_path: Path) -> None:
    tts = FakeTTS()
    speaker = PiperSpeaker(tts, FakePlayback(), out_dir=tmp_path)

    speaker.speak("a")
    speaker.flush()
    speaker.close()
    speaker.speak("b")  # must not raise after close
    assert tts.texts == ["a"]


def test_loop_drops_wake_while_speaker_is_playing(tmp_path: Path) -> None:
    # PR6 (item 6): while a reply is still being spoken, the loop must not
    # listen (no self-trigger on jarvis's own voice).
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True, True]),  # would fire if consulted
        capture=lambda: "abrí firefox",
        interpreter=FakeInterpreter([_interp()]),
        speaker=_StuckSpeaker(),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
    )

    outcome = run(pipeline, iterations=2)

    assert outcome == "speaking"
    assert pipeline.wake.calls == 0
    assert _StuckSpeaker.spoken == []


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


def _power_off_interp() -> Interpretation:
    return Interpretation(
        intent=Intent(
            intent="shutdown",
            entities={},
            confidence=0.9,
            confirm_required=True,
        ),
        needs_reask=False,
        unsupported=False,
    )


class _FlakySTT:
    """Succeeds, fails exactly once on the 2nd call, then succeeds again."""

    def __init__(self, good: str) -> None:
        self.good = good
        self.calls = 0

    def transcribe(self, wav_path: Path, duration_s: float) -> str:
        self.calls += 1
        if self.calls == 2:
            raise STTError("boom")
        return self.good


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


def test_loop_speaks_error_when_stt_fails_and_keeps_listening(
    tmp_path: Path,
) -> None:
    # PR6 (item 5): STT failure → spoken error, loop returns to listening.
    capturer = FakeCapturer([_speech(), _silence()])
    tts = FakeTTS()
    playback = FakePlayback()
    wake = FakeWake([True])
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=wake,
        capture=UtteranceCapture(capturer, FakeSTT("", error=True), _vad(), wav_dir=tmp_path),
        interpreter=FakeInterpreter([]),
        speaker=PiperSpeaker(tts, playback, out_dir=tmp_path),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        switch_state=MicSwitch(capturer, lambda: False),
    )

    outcome = run(pipeline, iterations=2)

    assert outcome == "stt_error"
    assert tts.texts == [STT_ERROR_SPOKEN]
    assert wake.calls == 1  # returned to listening after the error


def test_loop_confirmation_survives_stt_failure_and_retries(
    tmp_path: Path,
) -> None:
    # PR6 (item 5): a capture failure during confirmation must not abort the
    # destructive op silently — it apologizes and retries the confirmation.
    capturer = FakeCapturer(
        [_speech(), _speech(), _silence(), _speech(), _speech(), _silence(),
         _speech(), _speech(), _silence()]
    )
    stt = _FlakySTT("si")
    tts = FakeTTS()
    playback = FakePlayback()
    pipeline = Pipeline(
        clock=FakeClock(),
        wake=FakeWake([True]),
        capture=UtteranceCapture(capturer, stt, _vad(), wav_dir=tmp_path),
        interpreter=FakeInterpreter([_power_off_interp()]),
        speaker=PiperSpeaker(tts, playback, out_dir=tmp_path),
        executor=FakeExecutor(),
        session=load_state(str(tmp_path / "state.json")),
        cwd=str(tmp_path),
        git_runner=lambda cwd: "/repo",
        switch_state=MicSwitch(capturer, lambda: False),
    )

    outcome = run(pipeline, iterations=5)

    assert outcome == "executed"
    assert STT_ERROR_SPOKEN in tts.texts
    assert tts.texts[-1] == "ok"
    assert stt.calls == 3  # listen + failed confirm + successful confirm


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
