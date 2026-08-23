"""Audio capture tests (PR5, task 5.1).

Design (ADR-6): sounddevice streaming capture producing 16kHz mono float
blocks, an energy VAD that ends an utterance after 800ms of silence, and a
capturer interface (start/stop/read_frames) that is injectable so the
orchestrator loop runs on fakes without hardware.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from queue import Queue

import numpy as np
import pytest

from jarvis.audio.capture import (
    BLOCK_MS,
    SAMPLE_RATE,
    Capturer,
    SilenceVAD,
    SoundDeviceCapturer,
    gather_utterance,
    rms,
    write_wav,
)

BLOCK = SAMPLE_RATE * BLOCK_MS // 1000


def _sine(frames: int = BLOCK, amplitude: float = 0.5) -> np.ndarray:
    return (amplitude * np.sin(2 * np.pi * 220 * np.arange(frames) / SAMPLE_RATE)).astype(
        np.float32
    )


def _silence(frames: int = BLOCK) -> np.ndarray:
    return np.zeros(frames, dtype=np.float32)


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


def _vad(*, silence_s: float = 0.8, max_s: float = 10.0) -> SilenceVAD:
    return SilenceVAD(threshold=0.02, silence_s=silence_s, max_s=max_s)


# --- Pure energy helpers ------------------------------------------------------
def test_rms_zero_for_silence_and_positive_for_speech() -> None:
    assert rms(_silence()) == 0.0
    assert rms(_sine(amplitude=0.5)) > 0.0
    assert rms(_sine(amplitude=0.1)) < rms(_sine(amplitude=0.5))


def test_silence_vad_classifies_speech_and_silence() -> None:
    vad = _vad()
    assert vad.is_speech(_sine()) is True
    assert vad.is_speech(_silence()) is False


# --- gather_utterance: VAD gating --------------------------------------------
def test_gather_until_800ms_silence() -> None:
    vad = _vad(silence_s=0.1)
    capturer = FakeCapturer([_sine(), _sine(), _silence(), _sine()])
    blocks, duration = gather_utterance(capturer, vad)
    assert len(blocks) == 3
    assert duration == pytest.approx(0.3)
    assert capturer.reads == 3


def test_gather_stops_at_max_duration() -> None:
    vad = _vad(max_s=0.2, silence_s=0.8)
    capturer = FakeCapturer([_sine(), _sine(), _sine(), _sine()])
    blocks, duration = gather_utterance(capturer, vad)
    assert len(blocks) == 2
    assert duration == pytest.approx(0.2)


def test_gather_empty_when_no_frames() -> None:
    capturer = FakeCapturer([])
    blocks, duration = gather_utterance(capturer, _vad())
    assert blocks == []
    assert duration == 0.0


def test_gather_speech_only_without_silence_runs_to_max() -> None:
    vad = _vad(max_s=0.3, silence_s=0.8)
    capturer = FakeCapturer([_sine(), _sine(), _sine(), _sine(), _sine()])
    blocks, duration = gather_utterance(capturer, vad)
    assert len(blocks) == 3
    assert duration == pytest.approx(0.3)


# --- wav output ---------------------------------------------------------------
def test_write_wav_roundtrip(tmp_path: Path) -> None:
    import wave

    out = tmp_path / "utterance.wav"
    write_wav(out, [_sine(), _sine()], sample_rate=SAMPLE_RATE)
    with wave.open(str(out), "rb") as handle:
        assert handle.getframerate() == SAMPLE_RATE
        assert handle.getnchannels() == 1
        assert handle.getnframes() == 2 * BLOCK


def test_write_wav_single_block(tmp_path: Path) -> None:
    import wave

    out = tmp_path / "single.wav"
    write_wav(out, [_sine()], sample_rate=SAMPLE_RATE)
    with wave.open(str(out), "rb") as handle:
        assert handle.getnframes() == BLOCK


# --- SoundDeviceCapturer (no hardware: queued frames only) --------------------
def test_sounddevice_capturer_reads_queued_frames() -> None:
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    frame = _sine()
    capturer._queue.put(frame)
    assert capturer.read_frames(timeout=0.1) is frame
    assert capturer.read_frames(timeout=0.01) is None


def test_sounddevice_capturer_stop_without_start_is_noop() -> None:
    capturer = SoundDeviceCapturer()
    capturer.stop()  # must not raise


def test_capturer_is_a_protocol_matching_fakes() -> None:
    assert isinstance(FakeCapturer([]), Capturer)


# --- Noise-floor calibration (T-CALIB-01) ------------------------------------
def _noise_blocks(amplitude: float = 0.02, n: int = 6) -> list[np.ndarray]:
    """Ambient-noise blocks of a fixed amplitude (no loud speech)."""
    return [_sine(frames=BLOCK, amplitude=amplitude) for _ in range(n)]


def test_calibrate_raises_threshold_with_noise_floor() -> None:
    vad = SilenceVAD(threshold=0.5)  # start unrealistically high
    capturer = FakeCapturer(_noise_blocks(amplitude=0.05))
    new_threshold = vad.calibrate(
        capturer, ms=600, factor=1.2, min_threshold=0.01, read_timeout=0.1
    )
    # noise floor ~0.05 * 0.707 (RMS of a sine) ~ 0.035; *1.2 ~ 0.042
    assert new_threshold == pytest.approx(0.05 * 0.7071 * 1.2, rel=0.2)
    assert new_threshold < 0.5
    assert vad.threshold == new_threshold


def test_calibrate_floor_prevents_zero_threshold_on_silence() -> None:
    vad = SilenceVAD(threshold=0.02)
    capturer = FakeCapturer([_silence(), _silence(), _silence()])
    new_threshold = vad.calibrate(
        capturer, ms=300, factor=1.2, min_threshold=0.01, read_timeout=0.1
    )
    assert new_threshold >= 0.01
    assert vad.threshold >= 0.01


def test_calibrate_empty_capturer_keeps_min_threshold() -> None:
    vad = SilenceVAD(threshold=0.02)
    capturer = FakeCapturer([])  # no frames at all
    new_threshold = vad.calibrate(
        capturer, ms=500, factor=1.2, min_threshold=0.015, read_timeout=0.1
    )
    assert new_threshold == pytest.approx(0.015)


def test_utterance_capture_calibrates_energy_vad_before_gathering() -> None:
    """UtteranceCapture._calibrate() runs on energy VADs when calibrate_ms>0."""
    from jarvis.audio.pipeline import UtteranceCapture

    vad = SilenceVAD(threshold=0.5)
    # 3 ambient blocks for calibration + 1 speech block + silence tail
    blocks = _noise_blocks(amplitude=0.03, n=3)
    blocks += [_sine(amplitude=0.9), _silence()]
    capturer = FakeCapturer(blocks)
    stt = object()  # unused: capture returns None before STT (silence after speech)
    cap = UtteranceCapture(
        capturer,
        stt,
        vad,
        calibrate_ms=300,
        calibrate_factor=1.2,
        calibrate_min_threshold=0.01,
    )
    cap._calibrate()
    assert vad.threshold < 0.5
    assert vad.threshold >= 0.01


def test_utterance_capture_skips_calibration_when_ms_is_zero() -> None:
    from jarvis.audio.pipeline import UtteranceCapture

    vad = SilenceVAD(threshold=0.5)
    capturer = FakeCapturer(_noise_blocks(amplitude=0.05))
    cap = UtteranceCapture(capturer, object(), vad, calibrate_ms=0)
    cap._calibrate()
    assert vad.threshold == 0.5  # untouched


def test_utterance_capture_skips_calibration_for_silero_vad() -> None:
    """SileroVAD has no calibrate(); calibration is skipped (neural gate)."""
    from jarvis.audio.pipeline import UtteranceCapture

    silero = object()  # duck-typed stand-in without a calibrate method
    capturer = FakeCapturer(_noise_blocks(amplitude=0.05))
    cap = UtteranceCapture(capturer, object(), silero, calibrate_ms=300)
    cap._calibrate()  # must not raise
