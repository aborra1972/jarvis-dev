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
    OpenWakeWord,
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
    def __init__(self, blocks: list[np.ndarray] | None = None) -> None:
        self._queue = deque(blocks or [])
        self.started = 0
        self.stopped = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        return self._queue.popleft() if self._queue else None


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


# --- Pure threshold logic -----------------------------------------------------
def test_triggered_when_score_at_or_above_threshold() -> None:
    assert triggered({"hey_jarvis": 0.5}, 0.5) is True
    assert triggered({"hey_jarvis": 0.9, "marvin": 0.1}, 0.5) is True
    assert triggered({"marvin": 0.7}, 0.5) is True


def test_not_triggered_below_threshold_or_empty() -> None:
    assert triggered({"hey_jarvis": 0.49}, 0.5) is False
    assert triggered({}, 0.5) is False
    assert triggered({"hey_jarvis": 0.5, "marvin": 0.9}, 0.99) is False


# --- Model path resolution ----------------------------------------------------
def test_default_model_paths_use_openwakeword_hey_jarvis() -> None:
    paths = build_model_paths(None)
    assert len(paths) == 1
    assert paths[0].name == "hey_jarvis_v0.1.onnx"


def test_explicit_model_paths_are_preserved(tmp_path: Path) -> None:
    custom = tmp_path / "jarvis.onnx"
    custom.write_bytes(b"onnx")
    assert build_model_paths([custom]) == [custom]


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


def test_default_threshold_is_exposed() -> None:
    assert isinstance(DEFAULT_THRESHOLD, float)
