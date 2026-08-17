"""Streaming audio capture (PR5, task 5.1).

Design ADR-6: sounddevice streaming capture producing 16kHz mono float blocks,
plus an energy VAD that ends an utterance after 800ms of silence. The capture
layer is hardware-agnostic: the orchestrator loop runs against the Capturer
protocol with fakes (no mic) and swaps in SoundDeviceCapturer for real use.
"""

from __future__ import annotations

import wave
from queue import Empty, Queue
from typing import Protocol, runtime_checkable

import numpy as np

SAMPLE_RATE = 16000
BLOCK_MS = 100
SILENCE_MS = 800
MAX_UTTERANCE_S = 10.0

DEFAULT_THRESHOLD = 0.02


@runtime_checkable
class Capturer(Protocol):
    """Streaming frame source (mic in production, fake in tests)."""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        ...


def rms(block: np.ndarray) -> float:
    """Root-mean-square energy of a float32 audio block."""
    if block.size == 0:
        return 0.0
    return float(np.sqrt(float(np.mean(np.square(block)))))


class SilenceVAD:
    """Energy-based voice activity detector.

    A block counts as speech when its RMS equals or exceeds `threshold`.
    """

    def __init__(
        self,
        *,
        threshold: float = DEFAULT_THRESHOLD,
        silence_s: float = SILENCE_MS / 1000.0,
        max_s: float = MAX_UTTERANCE_S,
        sample_rate: int = SAMPLE_RATE,
        block_ms: int = BLOCK_MS,
    ) -> None:
        self.threshold = threshold
        self.silence_s = silence_s
        self.max_s = max_s
        self.sample_rate = sample_rate
        self.block_duration = block_ms / 1000.0

    def is_speech(self, block: np.ndarray) -> bool:
        return rms(block) >= self.threshold


class SoundDeviceCapturer:
    """sounddevice streaming capture (16kHz mono float) producing 100ms blocks.

    The stream is only opened on start(); read_frames() pops queued blocks so
    downstream code never blocks on the audio hardware directly.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, block_ms: int = BLOCK_MS) -> None:
        self.sample_rate = sample_rate
        self.block_ms = block_ms
        self._blocks = SAMPLE_RATE * block_ms // 1000
        self._queue: Queue[np.ndarray] = Queue()
        self._stream = None

    def start(self) -> None:
        if self._stream is not None:
            return
        import sounddevice as sd

        def _callback(indata: np.ndarray, frames: int, time, status) -> None:
            self._queue.put(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=self._blocks,
            callback=_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is None:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None


def gather_utterance(
    capturer: Capturer,
    vad: SilenceVAD,
    *,
    read_timeout: float = 1.0,
) -> tuple[list[np.ndarray], float]:
    """Collect frames until 800ms of trailing silence or max duration.

    Returns (blocks, duration_s). Blocks is empty when no frames arrive at all.
    The trailing-silence rule is the one in design Data Flow ("end of the
    utterance after 800ms of silence").
    """
    blocks: list[np.ndarray] = []
    silent_s = 0.0
    duration_s = 0.0
    while duration_s < vad.max_s:
        block = capturer.read_frames(timeout=read_timeout)
        if block is None:
            break
        blocks.append(block)
        duration_s += vad.block_duration
        silent_s = 0.0 if vad.is_speech(block) else silent_s + vad.block_duration
        if silent_s >= vad.silence_s:
            break
    return blocks, duration_s


def write_wav(path, blocks: list[np.ndarray], sample_rate: int = SAMPLE_RATE) -> None:
    """Write float32 blocks to a mono 16-bit WAV file.

    No-op if blocks is empty (guards against silence-only captures).
    """
    if not blocks:
        return
    data = np.concatenate(blocks) if len(blocks) > 1 else blocks[0]
    pcm = np.clip(data, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm16.tobytes())
