"""Audio capture tests (PR5, task 5.1).

Design (ADR-6): sounddevice streaming capture producing 16kHz mono float
blocks, an energy VAD that ends an utterance after 800ms of silence, and a
capturer interface (start/stop/read_frames) that is injectable so the
orchestrator loop runs on fakes without hardware.
"""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from queue import Queue
import time

import numpy as np
import pytest

from jarvis.audio.capture import (
    BLOCK_MS,
    SAMPLE_RATE,
    AudioMetrics,
    AudioMetricsPublisher,
    Capturer,
    SilenceVAD,
    SoundDeviceCapturer,
    gather_utterance,
    rms,
    write_wav,
    CaptureMode,
    CaptureStatus,
    gather_utterance_result,
)
import jarvis.config as config

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
        self.timeouts: list[float] = []

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        self.reads += 1
        self.timeouts.append(timeout)
        return self._queue.popleft() if self._queue else None


class FailingCapturer(FakeCapturer):
    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        self.reads += 1
        raise OSError("microphone unavailable")


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


def test_gather_initial_silence_does_not_trigger_trailing_silence_before_speech() -> None:
    """Trailing silence should be measured only after speech has started."""
    vad = _vad(silence_s=0.2, max_s=1.0)
    capturer = FakeCapturer(
        [_silence(), _silence(), _silence(), _sine(), _silence(), _silence(), _sine()]
    )

    blocks, duration = gather_utterance(capturer, vad)

    assert len(blocks) == 6
    assert duration == pytest.approx(0.6)
    assert any(vad.is_speech(block) for block in blocks)
    assert capturer.reads == 6


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


def test_gather_aborts_when_control_requests_stop() -> None:
    capturer = FakeCapturer([_sine(), _sine(), _sine()])

    blocks, duration = gather_utterance(
        capturer,
        _vad(),
        stop_requested=lambda: capturer.reads >= 1,
    )

    assert len(blocks) == 1
    assert duration == pytest.approx(0.1)


def test_gather_speech_only_without_silence_runs_to_max() -> None:
    vad = _vad(max_s=0.3, silence_s=0.8)
    capturer = FakeCapturer([_sine(), _sine(), _sine(), _sine(), _sine()])
    blocks, duration = gather_utterance(capturer, vad)
    assert len(blocks) == 3
    assert duration == pytest.approx(0.3)


# --- cancellable onset capture -----------------------------------------------
def test_ordinary_capture_waits_through_no_frames_and_bounds_preroll() -> None:
    idle = [_silence() for _ in range(5)]
    speech = _sine()
    result = gather_utterance_result(
        FakeCapturer([None, None, *idle, speech, _silence(), _silence()]),
        _vad(silence_s=0.2, max_s=0.3),
        mode=CaptureMode.ORDINARY,
        idle_preroll_blocks=2,
    )
    assert result.status is CaptureStatus.UTTERANCE
    assert result.onset_seen is True
    assert len(result.blocks) == 5
    assert result.blocks[2] is speech
    assert result.duration_s == pytest.approx(0.3)
    assert result.no_frame_polls == 2


def test_capture_cancellation_and_device_failure_are_distinct() -> None:
    cancelled = gather_utterance_result(
        FakeCapturer([_silence(), _sine()]), _vad(), stop_requested=lambda: True
    )
    failed = gather_utterance_result(FailingCapturer([]), _vad())
    assert cancelled.status is CaptureStatus.CANCELLED
    assert failed.status is CaptureStatus.DEVICE_FAILURE


def test_cancellation_during_collection_returns_no_dispatchable_audio() -> None:
    capturer = FakeCapturer([_sine(), _sine(), _silence()])
    result = gather_utterance_result(
        capturer,
        _vad(),
        stop_requested=lambda: capturer.reads >= 2,
    )
    assert result.status is CaptureStatus.CANCELLED
    assert result.blocks == ()


def test_post_onset_duration_excludes_pre_onset_wait() -> None:
    result = gather_utterance_result(
        FakeCapturer([_silence(), _silence(), _sine(), _sine(), _sine()]),
        _vad(max_s=0.2, silence_s=0.8),
        idle_preroll_blocks=2,
    )
    assert result.status is CaptureStatus.UTTERANCE
    assert result.duration_s == pytest.approx(0.2)
    assert len(result.blocks) == 4


def test_confirmation_mode_has_a_finite_deadline() -> None:
    result = gather_utterance_result(
        FakeCapturer([_silence()] * 10),
        _vad(),
        mode=CaptureMode.CONFIRMATION,
        deadline=0.0,
        clock=lambda: 1.0,
    )
    assert result.status is CaptureStatus.CANCELLED


def test_capture_defaults_use_audio_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "AUDIO_PREROLL_S", 0.3)
    monkeypatch.setattr(config, "AUDIO_READ_POLL_S", 0.07)
    capturer = FakeCapturer([_silence() for _ in range(25)] + [_sine(), _silence(), _silence()])
    result = gather_utterance_result(capturer, _vad(silence_s=0.2, max_s=0.3))

    assert result.status is CaptureStatus.UTTERANCE
    assert len(result.blocks) == 6  # three configured pre-roll blocks plus utterance
    assert capturer.timeouts == [0.07] * 28


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
def test_audio_metrics_publisher_writes_json_snapshot_atomically(tmp_path: Path) -> None:
    metrics = AudioMetrics(pcm_frames_received=123, empty_reads=2, wake_wait_results=[True])
    path = tmp_path / "audio_metrics.json"
    publisher = AudioMetricsPublisher(metrics, path, interval_s=0.01)

    publisher.publish_once()

    assert json.loads(path.read_text()) == {
        "pcm_frames_received": 123,
        "queue_frames_read": 0,
        "front_frames_read": 0,
        "empty_reads": 2,
        "replayed_preroll_frames": 0,
        "wake_wait_attempts": 0,
        "wake_wait_results": [True],
    }
    assert not list(tmp_path.glob("*.tmp"))


def test_audio_metrics_publisher_refreshes_and_stops(tmp_path: Path) -> None:
    metrics = AudioMetrics()
    path = tmp_path / "audio_metrics.json"
    publisher = AudioMetricsPublisher(metrics, path, interval_s=0.01)
    publisher.start()
    try:
        metrics.empty_reads = 7
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            if path.exists() and json.loads(path.read_text())["empty_reads"] == 7:
                break
            time.sleep(0.01)
        assert json.loads(path.read_text())["empty_reads"] == 7
        assert publisher._thread is not None and publisher._thread.daemon
    finally:
        publisher.stop()
    assert publisher._thread is None


def test_sounddevice_capturer_reads_queued_frames() -> None:
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    frame = _sine()
    capturer._queue.put(frame)
    assert capturer.read_frames(timeout=0.1) is frame
    assert capturer.read_frames(timeout=0.01) is None


def test_sounddevice_capturer_records_frame_counters_and_empty_reads() -> None:
    metrics = AudioMetrics()
    capturer = SoundDeviceCapturer(metrics=metrics)
    frame = _sine(frames=123)
    capturer._queue.put(frame)

    assert capturer.read_frames(timeout=0.1) is frame
    assert capturer.read_frames(timeout=0.01) is None
    assert metrics.queue_frames_read == 123
    assert metrics.empty_reads == 1


def test_sounddevice_capturer_block_count_uses_sample_rate() -> None:
    capturer = SoundDeviceCapturer(sample_rate=8000, block_ms=100)

    assert capturer._blocks == 800


def test_sounddevice_capturer_flush_drains_stale_buffer() -> None:
    """flush() discards queued audio (T-FLUSH-01, post-playback stale mic)."""
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    # 5 stale blocks queued from Jarvis's own reply audio
    for _ in range(5):
        capturer._queue.put(_sine())
    # flush 1s = 10 blocks of 100ms — drains all 5 present
    capturer.flush(ms=1000)
    assert capturer._queue.empty()
    assert capturer.read_frames(timeout=0.01) is None


def test_sounddevice_capturer_flush_partial_when_fewer_blocks() -> None:
    """flush() drains what's there and doesn't hang on an empty tail."""
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    capturer._queue.put(_sine())  # only 1 stale block
    capturer.flush(ms=1000)  # wants 10, drains the 1
    assert capturer._queue.empty()


def test_sounddevice_capturer_flush_zero_ms_drains_at_least_one() -> None:
    """flush(0) still drains one block (never leaves a stale head)."""
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    capturer._queue.put(_sine())
    capturer.flush(ms=0)
    assert capturer._queue.empty()


def test_sounddevice_capturer_stop_without_start_is_noop() -> None:
    capturer = SoundDeviceCapturer()
    capturer.stop()  # must not raise


def test_enqueue_back_reads_front_blocks_first() -> None:
    """Re-injected pre-roll (name wake) is read BEFORE live queued frames."""
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    queued_a, queued_b = _sine(), _sine()
    capturer._queue.put(queued_a)
    capturer._queue.put(queued_b)
    f0, f1 = _sine(), _sine()
    capturer.enqueue_back([f0, f1])
    assert capturer.read_frames(timeout=0.01) is f0
    assert capturer.read_frames(timeout=0.01) is f1
    assert capturer.read_frames(timeout=0.01) is queued_a
    assert capturer.read_frames(timeout=0.01) is queued_b


def test_enqueue_back_marks_replayed_preroll_for_one_capture() -> None:
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    capturer.enqueue_back([_sine()])

    assert capturer.consume_replayed_preroll() is True
    assert capturer.consume_replayed_preroll() is False


def test_flush_drains_front_and_queue() -> None:
    """flush() must discard the re-injected front buffer too (T-FLUSH-01)."""
    capturer = SoundDeviceCapturer(sample_rate=SAMPLE_RATE, block_ms=BLOCK_MS)
    capturer.enqueue_back([_sine(), _sine()])
    capturer._queue.put(_sine())
    capturer.flush(ms=1)
    assert not capturer._front
    assert capturer._queue.empty()
    assert capturer.read_frames(timeout=0.01) is None


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
