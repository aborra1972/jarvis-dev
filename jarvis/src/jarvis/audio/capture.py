"""Streaming audio capture (PR5, task 5.1).

Design ADR-6: sounddevice streaming capture producing 16kHz mono float blocks,
plus an energy VAD that ends an utterance after 800ms of silence. The capture
layer is hardware-agnostic: the orchestrator loop runs against the Capturer
protocol with fakes (no mic) and swaps in SoundDeviceCapturer for real use.
"""

from __future__ import annotations

from collections import deque
import wave
from queue import Empty, Queue
from typing import Callable, Protocol, runtime_checkable

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

    def calibrate(
        self,
        capturer: Capturer,
        *,
        ms: int = 500,
        factor: float = 1.2,
        min_threshold: float = DEFAULT_THRESHOLD,
        read_timeout: float = 1.0,
    ) -> float:
        """Measure ambient noise and raise the energy threshold (T-CALIB-01).

        Reads up to ``ms`` of ambient audio from the capturer, computes the
        RMS noise floor, and sets ``self.threshold`` to
        ``max(noise_floor * factor, min_threshold)``. Returns the new
        threshold. A floor keeps the gate from collapsing to 0 on silence.
        """
        samples = int(self.sample_rate * ms / 1000.0)
        collected = 0
        sq_sum = 0.0
        count = 0
        while collected < samples:
            block = capturer.read_frames(timeout=read_timeout)
            if block is None:
                break
            flat = np.asarray(block, dtype=np.float32).reshape(-1)
            if flat.size == 0:
                continue
            sq_sum += float(np.sum(flat * flat))
            count += flat.size
            collected += flat.size
        noise_floor = float(np.sqrt(sq_sum / count)) if count else 0.0
        self.threshold = max(noise_floor * factor, min_threshold)
        return self.threshold


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
        # Re-injected pre-roll (name-gated wake): read BEFORE live frames.
        self._front: deque[np.ndarray] = deque()
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
        if self._front:
            return self._front.popleft()
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None

    def enqueue_back(self, blocks) -> None:
        """Insert blocks at the FRONT of the read stream, preserving order.

        Used by the name-gated wake (engine "name"): SpeechStartWake keeps a
        pre-roll of the last ~2s (which contains the agent name the user is
        speaking RIGHT NOW); when it fires, rewind() re-injects these blocks
        so the utterance capture reads the name before any live audio.
        """
        self._front.extendleft(reversed(list(blocks)))

    def flush(self, ms: int = 1000) -> None:
        """Discard up to ``ms`` of queued audio (post-playback stale mic).

        T-FLUSH-01: after TTS playback the mic may have captured Jarvis's own
        voice; that audio lingers in the queue and can trigger a false wake on
        the next cycle. This drains the buffered blocks for up to ``ms`` so the
        wake detector only sees fresh, post-reply audio. The re-injected
        pre-roll front buffer (name wake) is drained entirely first — it is
        bounded by the pre-roll window and is stale by definition.
        """
        while self._front:
            self._front.popleft()
        n_blocks = max(int(ms / self.block_ms), 1)
        for _ in range(n_blocks):
            try:
                self._queue.get_nowait()
            except Empty:
                break


def gather_utterance(
    capturer: Capturer,
    vad: SilenceVAD,
    *,
    read_timeout: float = 1.0,
    stop_requested: Callable[[], bool] | None = None,
) -> tuple[list[np.ndarray], float]:
    """Collect frames until 800ms of trailing silence or max duration.

    Returns (blocks, duration_s). Blocks is empty when no frames arrive at all.
    The trailing-silence rule is the one in design Data Flow ("end of the
    utterance after 800ms of silence").
    """
    blocks: list[np.ndarray] = []
    silent_s = 0.0
    duration_s = 0.0
    speech_started = False
    while duration_s < vad.max_s:
        if stop_requested is not None and stop_requested():
            break
        block = capturer.read_frames(timeout=read_timeout)
        if block is None:
            break
        blocks.append(block)
        duration_s += vad.block_duration
        if vad.is_speech(block):
            speech_started = True
            silent_s = 0.0
        elif speech_started:
            silent_s += vad.block_duration
        if speech_started and silent_s >= vad.silence_s:
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


# --- Silero VAD (T-VAD-02) ---
class SileroVAD:
    """Silero VAD-based voice activity detector (offline ONNX model).

    Scores each captured block for speech probability instead of raw RMS
    energy. Much more robust than a fixed amplitude threshold against
    ambient noise (fans, traffic, hum, keyboard clicks) because it was
    trained to recognize speech patterns, not just "loud vs quiet".

    The model comes from the pip ``silero-vad`` package via
    ``load_silero_vad(onnx=True)`` (offline ONNX runtime), loaded lazily on
    first use. Falls back to energy-based SilenceVAD if the model fails to
    load / the package isn't installed.

    Implements the same duck-typed interface the capture pipeline needs:
    ``is_speech(block)``, ``block_duration``, ``max_s``, ``silence_s`` and
    ``sample_rate``, so it can replace SilenceVAD as a drop-in (T-VAD-02).
    """

    def __init__(
        self,
        *,
        threshold: float = 0.5,
        sample_rate: int = SAMPLE_RATE,
        block_ms: int = BLOCK_MS,
        silence_s: float = SILENCE_MS / 1000.0,
        max_s: float = MAX_UTTERANCE_S,
    ) -> None:
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.block_duration = block_ms / 1000.0
        self.silence_s = silence_s
        self.max_s = max_s
        self._model = None
        self._init_failed = False
        self._buffer = np.array([], dtype=np.float32)

    def _ensure_loaded(self) -> bool:
        """Lazily load the Silero VAD model (offline ONNX)."""
        if self._model is not None:
            return True
        if self._init_failed:
            return False
        try:
            from silero_vad import load_silero_vad

            self._model = load_silero_vad(onnx=True)
            return True
        except Exception:
            self._init_failed = True
            return False

    def is_speech(self, block: np.ndarray) -> bool:
        """Check if a block contains speech using Silero VAD.

        Falls back to energy-based detection if Silero model failed to load.
        """
        if block.size == 0:
            return False

        if not self._ensure_loaded():
            # Fallback to simple energy VAD
            return rms(block) >= DEFAULT_THRESHOLD

        # Silero accepts fixed 32 ms frames: 512 samples at 16 kHz (256 at
        # 8 kHz). Capture blocks are normally 100 ms, so score every frame and
        # pad only the final remainder instead of passing an invalid shape.
        import torch

        if block.ndim > 1:
            block = block.reshape(-1)
        samples = np.ascontiguousarray(block, dtype=np.float32)
        if self._buffer.size:
            samples = np.concatenate((self._buffer, samples))
        frame_samples = 512 if self.sample_rate == 16000 else 256
        complete_samples = samples.size - (samples.size % frame_samples)
        self._buffer = samples[complete_samples:]
        max_probability = 0.0
        for offset in range(0, complete_samples, frame_samples):
            frame = samples[offset : offset + frame_samples]
            tensor = torch.from_numpy(frame)
            with torch.no_grad():
                prob = float(self._model(tensor, self.sample_rate).item())
            max_probability = max(max_probability, prob)
        return max_probability >= self.threshold

    def reset(self) -> None:
        """Clear buffered audio and the model's recurrent state."""
        self._buffer = np.array([], dtype=np.float32)
        reset_states = getattr(self._model, "reset_states", None)
        if callable(reset_states):
            reset_states()


def build_vad(
    *,
    engine: str = "silero",
    threshold: float | None = None,
    silence_s: float = SILENCE_MS / 1000.0,
    max_s: float = MAX_UTTERANCE_S,
    sample_rate: int = SAMPLE_RATE,
    block_ms: int = BLOCK_MS,
) -> SileroVAD | SilenceVAD:
    """Factory: build the configured VAD, falling back to energy on failure.

    engine="silero" (default) tries the Silero model first; if it can't
    load (package not installed, model not cached, offline first-run with
    no network), falls back to the energy-based SilenceVAD so Jarvis still
    starts instead of crashing. Construction is side-effect free here (the
    Silero model loads lazily on first is_speech call), so this is safe to
    call from unit tests.
    """
    if engine == "silero":
        try:
            return SileroVAD(
                threshold=threshold if threshold is not None else 0.5,
                silence_s=silence_s,
                max_s=max_s,
                sample_rate=sample_rate,
                block_ms=block_ms,
            )
        except Exception as exc:  # pragma: no cover - environment dependent
            print(
                f"[jarvis] WARN: Silero VAD no cargó ({exc}); usando energy VAD",
                flush=True,
            )
    return SilenceVAD(
        threshold=threshold if threshold is not None else DEFAULT_THRESHOLD,
        silence_s=silence_s,
        max_s=max_s,
        sample_rate=sample_rate,
        block_ms=block_ms,
    )


def calibrate_noise_floor(
    capturer: Capturer,
    *,
    duration_s: float = 1.2,
    multiplier: float = 2.5,
    min_threshold: float = 0.01,
    max_threshold: float = 0.12,
    read_timeout: float = 1.0,
) -> float:
    """Sample ambient noise and derive a VAD threshold for this environment.

    Call once at boot (mic must already be started). Reads ~duration_s of
    silence, takes the mean RMS, and scales it by `multiplier` so speech
    (which sits well above ambient noise) still crosses the gate. Falls back
    to DEFAULT_THRESHOLD if no frames arrive (mic not ready / muted).
    """
    samples: list[float] = []
    elapsed = 0.0
    block_duration = BLOCK_MS / 1000.0
    while elapsed < duration_s:
        block = capturer.read_frames(timeout=read_timeout)
        if block is None:
            break
        samples.append(rms(block))
        elapsed += block_duration
    if not samples:
        return DEFAULT_THRESHOLD
    noise_floor = float(np.mean(samples))
    threshold = noise_floor * multiplier
    return max(min_threshold, min(threshold, max_threshold))
