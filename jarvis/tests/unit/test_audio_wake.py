"""Wake-word detection tests (PR5, task 5.2).

Design ADR-3: openWakeWord wrapper gated by a configurable threshold. The
detector implements the orchestrator WakeDetector protocol (wait(timeout) ->
bool, PR3) and pulls frames from a Capturer. Tests use a fake model and a fake
capturer so no ONNX runtime or mic is involved.

Verified against openwakeword 0.4.0 (PR5): Model(wakeword_model_paths=[...])
is the current API, predict(x) returns {model_name: score}, and the
pretrained hey_jarvis_v0.1.onnx ships with the package.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path

import numpy as np
import pytest

from jarvis.audio.capture import SAMPLE_RATE, BLOCK_MS
from jarvis.audio.wake import (
    DEFAULT_THRESHOLD,
    DEFAULT_VAD_THRESHOLD,
    OpenWakeWord,
    SpeechStartWake,
    XLSRWakeWord,
    _positive_class_probability,
    build_wake_detector,
    build_model_paths,
    triggered,
)

BLOCK = SAMPLE_RATE * BLOCK_MS // 1000


class FakeModel:
    """Scripted stand-in for openwakeword.Model.predict."""

    def __init__(self, scores: list[dict[str, float]]) -> None:
        self.scores = scores
        self.predicts = 0

    def predict(self, block: np.ndarray) -> dict[str, float]:
        self.predicts += 1
        return self.scores.pop(0)


class FakeCapturer:
    """Models SoundDeviceCapturer: re-injected pre-roll is read from `_front`
    before the live frames in `_queue`."""

    def __init__(self, blocks: list[np.ndarray] | None = None) -> None:
        self._queue = deque(blocks or [])
        self._front: deque[np.ndarray] = deque()
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        if self._front:
            return self._front.popleft()
        return self._queue.popleft() if self._queue else None

    def enqueue_back(self, blocks) -> None:
        self._front.extendleft(reversed(list(blocks)))


def _frame(freq: int = 440) -> np.ndarray:
    return (0.3 * np.sin(2 * np.pi * freq * np.arange(BLOCK) / SAMPLE_RATE)).astype(
        np.float32
    )


class FakeClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FakeVAD:
    """Scripted stand-in for the VAD used by SpeechStartWake."""

    def __init__(self, script: list[bool]) -> None:
        self.script = deque(script)
        self.resets = 0

    def is_speech(self, block: np.ndarray) -> bool:
        return self.script.popleft() if self.script else False

    def reset(self) -> None:
        self.resets += 1


# --- Pure threshold logic -----------------------------------------------------
def test_triggered_when_score_at_or_above_threshold() -> None:
    assert triggered({"hey_jarvis": 0.5}, 0.5) is True
    assert triggered({"hey_jarvis": 0.9, "marvin": 0.1}, 0.5) is True
    assert triggered({"marvin": 0.7}, 0.5) is True


def test_not_triggered_below_threshold_or_empty() -> None:
    assert triggered({"hey_jarvis": 0.49}, 0.5) is False
    assert triggered({}, 0.5) is False
    assert triggered({"hey_jarvis": 0.5, "marvin": 0.9}, 0.99) is False


def test_xlsr_reads_probability_output_instead_of_binary_label() -> None:
    outputs = [np.array([1]), [{0: 0.12, 1: 0.88}]]

    assert _positive_class_probability(outputs) == pytest.approx(0.88)


def test_xlsr_supports_tensor_probability_output() -> None:
    outputs = [np.array([0]), np.array([[0.73, 0.27]], dtype=np.float32)]

    assert _positive_class_probability(outputs) == pytest.approx(0.27)


# --- Model path resolution ----------------------------------------------------
def test_default_model_paths_use_openwakeword_hey_jarvis() -> None:
    paths = build_model_paths(None)
    assert len(paths) == 1
    assert paths[0].name == "hey_jarvis_v0.1.onnx"


def test_explicit_model_paths_are_preserved(tmp_path: Path) -> None:
    custom = tmp_path / "jarvis.onnx"
    custom.write_bytes(b"onnx")
    assert build_model_paths([custom]) == [custom]


def test_build_wake_detector_returns_openwakeword_backend() -> None:
    detector = build_wake_detector(
        FakeCapturer(),
        engine="openwakeword",
        model=FakeModel([]),
    )

    assert isinstance(detector, OpenWakeWord)


# --- OpenWakeWord.wait --------------------------------------------------------
def test_wait_triggers_when_score_exceeds_threshold() -> None:
    model = FakeModel([{"hey_jarvis": 0.9}])
    wake = OpenWakeWord(
        capturer=FakeCapturer([_frame()]),
        model=model,
        threshold=0.5,
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is True
    assert model.predicts == 1


def test_wait_returns_false_without_trigger_before_timeout() -> None:
    model = FakeModel([{"hey_jarvis": 0.2}, {"hey_jarvis": 0.2}])
    clock = FakeClock()
    wake = OpenWakeWord(
        capturer=FakeCapturer([_frame(), _frame()]),
        model=model,
        threshold=0.5,
        clock=clock,
    )
    assert wake.wait(timeout=5.0) is False
    assert model.predicts == 2


def test_wait_stops_at_timeout_even_with_frames_remaining() -> None:
    clock = FakeClock()
    wake = OpenWakeWord(
        capturer=FakeCapturer([_frame(), _frame(), _frame()]),
        model=FakeModel([{"hey_jarvis": 0.2}, {"hey_jarvis": 0.2}, {"hey_jarvis": 0.2}]),
        threshold=0.5,
        clock=clock,
    )
    clock.advance(10.0)
    assert wake.wait(timeout=1.0) is False


def test_wait_returns_false_when_capturer_dries_up() -> None:
    clock = FakeClock()
    wake = OpenWakeWord(
        capturer=FakeCapturer([_frame()]),
        model=FakeModel([{"hey_jarvis": 0.2}]),
        threshold=0.5,
        clock=clock,
    )
    assert wake.wait(timeout=10.0) is False


def test_wait_retries_transient_empty_read() -> None:
    model = FakeModel([{"hey_jarvis": 0.9}])
    wake = OpenWakeWord(
        capturer=FakeCapturer([None, _frame()]),
        model=model,
        threshold=0.5,
        clock=FakeClock(),
    )

    assert wake.wait(timeout=1.0) is True
    assert model.predicts == 1


def test_wait_bounds_empty_read_retries() -> None:
    model = FakeModel([])
    wake = OpenWakeWord(
        capturer=FakeCapturer([None, None, None, None]),
        model=model,
        threshold=0.5,
        clock=FakeClock(),
    )

    assert wake.wait(timeout=1.0) is False
    assert len(wake.capturer._queue) == 1


def test_wait_flattens_and_scales_float_blocks_before_predict() -> None:
    """Regression: sounddevice delivers (frames, 1) float32; openwakeword needs
    flat int16 PCM.

    The 2D shape made the melspectrogram Conv fail with "Invalid input shape"
    on the first block, crashing jarvis start at the first wake scan. The raw
    normalized floats would also truncate to silence inside openwakeword's
    int16 cast, so float blocks must be rescaled to int16 before predict.
    """

    class RecordingModel(FakeModel):
        def __init__(self) -> None:
            super().__init__([{"hey_jarvis": 0.2}])
            self.seen: list[np.ndarray] = []

        def predict(self, block: np.ndarray) -> dict[str, float]:
            self.seen.append(block)
            return super().predict(block)

    model = RecordingModel()
    wake = OpenWakeWord(
        capturer=FakeCapturer([_frame().reshape(-1, 1)]),
        model=model,
        threshold=0.5,
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is False
    assert model.seen[0].ndim == 1
    assert model.seen[0].shape == (BLOCK,)
    assert model.seen[0].dtype == np.int16
    # 0.3 amplitude -> ~9830 int16, not truncated to 0
    assert np.abs(model.seen[0]).max() > 5000


def test_default_threshold_is_exposed() -> None:
    assert isinstance(DEFAULT_THRESHOLD, float)


# --- SpeechStartWake: name-gated wake (engine "name") -------------------------
def test_retries_transient_empty_read() -> None:
    wake = SpeechStartWake(
        capturer=FakeCapturer([None, _frame()]),
        vad=FakeVAD([True]),
        clock=FakeClock(),
    )

    assert wake.wait(timeout=1.0) is True


def test_fires_on_leading_edge_of_speech() -> None:
    speech = [False, False, True, True, False, True]
    capturer = FakeCapturer([_frame() for _ in speech])
    wake = SpeechStartWake(
        capturer=capturer,
        vad=FakeVAD(speech),
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is True
    assert len(capturer._queue) == 3  # consumed exactly 3 blocks
    assert wake._was_speech is True


def test_does_not_fire_when_speech_already_in_progress() -> None:
    capturer = FakeCapturer([_frame() for _ in range(4)])
    wake = SpeechStartWake(
        capturer=capturer,
        vad=FakeVAD([False, True, True, True]),
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is True  # fires on the 2nd block
    assert wake.wait(timeout=1.0) is False  # already speaking: no leading edge


def test_returns_false_on_timeout_with_no_speech() -> None:
    clock = FakeClock()
    wake = SpeechStartWake(
        capturer=FakeCapturer([_frame(), _frame()]),
        vad=FakeVAD([False, False]),
        clock=clock,
    )
    clock.advance(10.0)
    assert wake.wait(timeout=1.0) is False


def test_returns_false_when_capturer_dries_up() -> None:
    wake = SpeechStartWake(
        capturer=FakeCapturer([]),
        vad=FakeVAD([]),
        clock=FakeClock(),
    )
    assert wake.wait(timeout=10.0) is False


def test_xlsr_retries_transient_empty_read(monkeypatch: pytest.MonkeyPatch) -> None:
    wake = XLSRWakeWord(
        capturer=FakeCapturer([None, _frame()]),
        classifier_path=Path("unused.onnx"),
        window_s=BLOCK / SAMPLE_RATE,
        hop_s=BLOCK / SAMPLE_RATE,
        model=object(),
        clock=FakeClock(),
    )
    monkeypatch.setattr(wake, "_classify", lambda window: 0.9)

    assert wake.wait(timeout=1.0) is True


def test_rewind_reinjects_preroll_in_order() -> None:
    speech = _frame()
    capturer = FakeCapturer([speech])
    wake = SpeechStartWake(
        capturer=capturer,
        vad=FakeVAD([True]),
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is True
    assert wake.rewind() is True
    assert capturer.read_frames() is speech  # the fired block is re-injected


def test_rewind_with_two_preroll_blocks_preserves_order() -> None:
    silence = np.zeros(BLOCK, dtype=np.float32)
    speech = _frame()
    capturer = FakeCapturer([silence, speech])
    wake = SpeechStartWake(
        capturer=capturer,
        vad=FakeVAD([False, True]),
        clock=FakeClock(),
    )
    assert wake.wait(timeout=1.0) is True
    assert wake.rewind() is True
    # Original read order must be preserved: silence, then speech.
    assert capturer.read_frames() is silence
    assert capturer.read_frames() is speech


def test_flush_clears_preroll_and_resets_leading_edge() -> None:
    capturer = FakeCapturer([_frame(), _frame()])
    vad = FakeVAD([True, True])
    wake = SpeechStartWake(capturer=capturer, vad=vad, clock=FakeClock())
    assert wake.wait(timeout=1.0) is True
    assert wake._preroll
    wake.flush()
    assert not wake._preroll
    assert wake._preroll_samples == 0
    assert wake._was_speech is False
    assert vad.resets == 1


def test_gates_by_name_flag_is_true() -> None:
    wake = SpeechStartWake(capturer=FakeCapturer(), vad=FakeVAD([]))
    assert wake.gates_by_name is True


def test_build_wake_detector_name_engine() -> None:
    detector = build_wake_detector(FakeCapturer(), engine="name")
    assert isinstance(detector, SpeechStartWake)
    assert DEFAULT_VAD_THRESHOLD == 0.6  # Silero speech-probability gate
