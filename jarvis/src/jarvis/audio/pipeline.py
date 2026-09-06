"""Voice adapters wiring the audio layer to the orchestrator (PR5, item 6).

The loop (PR3) consumes three contracts:
- Capture: UtteranceCapture — capturer + VAD + STT -> transcript or None.
- Speaker: PiperSpeaker — TTS + playback for the spoken reply.
- switch_state (RF-11): MicSwitch — off releases the mic and the wake
  detector stays idle; on resumes capture. Reactivation is non-vocal only.

Real hardware (sounddevice / whisper-cli / piper / paplay) is swapped in via
config at E2E (PR6); these adapters only depend on the audio interfaces.
"""

from __future__ import annotations

import logging
import os
import queue
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

import numpy as np

from jarvis.audio.capture import (
    SAMPLE_RATE,
    DEFAULT_THRESHOLD,
    Capturer,
    SilenceVAD,
    SileroVAD,
    gather_utterance,
    rms,
    write_wav,
)
from jarvis.audio.playback import PlaybackError
from jarvis.audio.stt import STTError
from jarvis.audio.tts import TTSError
from jarvis.orchestrator.contracts import CaptureError

logger = logging.getLogger("jarvis.audio")

# After this many consecutive TTS/playback failures, surface a visible warning.
# A single failure is normal (network blip); 3+ means something is systematically
# wrong (edge-tts binary missing, network down, speakers broken).
_MAX_CONSECUTIVE_TTS_FAILURES = 3


class UtteranceCapture:
    """Captures a spoken utterance and transcribes it (contracts.Capture).

    Returns None for silence so the loop stays idle (spec: no self-trigger on
    non-vocal noise). STT failures raise CaptureError so the loop speaks an
    apology and retries (PR6, item 5) instead of staying silently idle.
    """

    def __init__(
        self,
        capturer: Capturer,
        stt: object,
        vad: SilenceVAD | SileroVAD,
        *,
        sample_rate: int = SAMPLE_RATE,
        read_timeout: float = 1.0,
        wav_dir: Path | None = None,
        calibrate_ms: int = 0,
        calibrate_factor: float = 1.2,
        calibrate_min_threshold: float = 0.01,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self.capturer = capturer
        self.stt = stt
        self.vad = vad
        self.sample_rate = sample_rate
        self.read_timeout = read_timeout
        self.wav_dir = Path(wav_dir) if wav_dir else Path(tempfile.gettempdir())
        self._last_audio: np.ndarray | None = None
        self._calibrate_ms = calibrate_ms
        self._calibrate_factor = calibrate_factor
        self._calibrate_min_threshold = calibrate_min_threshold
        self._stop_requested = stop_requested

    def _calibrate(self) -> None:
        """Measure ambient noise right after the wake word (T-CALIB-01).

        Only energy-based VADs (SilenceVAD) expose ``calibrate``; Silero's
        neural gate already discriminates by model confidence, so it is skipped.
        """
        calibrate = getattr(self.vad, "calibrate", None)
        if calibrate is None or self._calibrate_ms <= 0:
            return
        calibrate(
            self.capturer,
            ms=self._calibrate_ms,
            factor=self._calibrate_factor,
            min_threshold=self._calibrate_min_threshold,
            read_timeout=self.read_timeout,
        )

    def _next_wav(self) -> Path:
        return self.wav_dir / f"jarvis-capture-{uuid.uuid4().hex}.wav"

    def capture(self) -> str | None:
        reset = getattr(self.vad, "reset", None)
        if callable(reset):
            reset()
        self._calibrate()
        blocks, duration_s = gather_utterance(
            self.capturer,
            self.vad,
            read_timeout=self.read_timeout,
            stop_requested=self._stop_requested,
        )
        if self._stop_requested is not None and self._stop_requested():
            return None
        if not blocks or not any(rms(block) >= DEFAULT_THRESHOLD for block in blocks):
            return None
        # Store audio for speaker verification (before STT deletes the file)
        audio = np.concatenate(blocks) if len(blocks) > 1 else blocks[0]
        self._last_audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        wav_path = self._next_wav()
        write_wav(wav_path, blocks, sample_rate=self.sample_rate)
        try:
            return self.stt.transcribe(wav_path, duration_s)
        except STTError as exc:
            raise CaptureError(str(exc)) from exc
        finally:
            wav_path.unlink(missing_ok=True)

    def last_audio(self) -> np.ndarray | None:
        """Return the last captured audio array (float32, 16kHz mono).

        Used by the orchestrator for speaker verification. Returns None
        if no audio has been captured yet.
        """
        return self._last_audio


class PiperSpeaker:
    """Synthesizes and plays spoken replies on a worker thread (contracts.Speaker).

    Drives any TTS backend (PiperTTS offline, EdgeTTS neural — the output
    suffix comes from ``tts.extension``). PR6 (item 6): TTS is slow (seconds
    per reply), so ``speak()`` enqueues and returns immediately — the loop
    never blocks on TTS and replies play in order. ``is_playing()`` feeds the
    loop's IDLE gate (no self-trigger on jarvis's own voice); ``flush()``
    waits until the queue drains (used by the loop on exit and by tests);
    ``close()`` stops the worker.
    """

    def __init__(
        self,
        tts: object,
        playback: object,
        *,
        out_dir: Path | None = None,
    ) -> None:
        self.tts = tts
        self.playback = playback
        self.out_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir())
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._closed = False
        self._playing = False
        self._consecutive_tts_failures: int = 0
        self._thread = threading.Thread(target=self._worker, name="jarvis-piper", daemon=True)
        self._thread.start()

    def _next_media(self) -> Path:
        ext = getattr(self.tts, "extension", ".wav")
        return self.out_dir / f"jarvis-reply-{uuid.uuid4().hex}{ext}"

    def _worker(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:  # stop sentinel
                return
            self._playing = True
            try:
                self._play(text)
            finally:
                self._playing = False
                self._queue.task_done()

    def _play(self, text: str) -> None:
        media_path = self._next_media()
        try:
            media_path = self.tts.synthesize(text, media_path)
            self.playback.play(media_path)
            self._consecutive_tts_failures = 0  # reset on success
        except (TTSError, PlaybackError) as exc:
            self._consecutive_tts_failures += 1
            logger.warning(
                "TTS/playback failure (%d consecutive): %s",
                self._consecutive_tts_failures, exc,
            )
            if self._consecutive_tts_failures >= _MAX_CONSECUTIVE_TTS_FAILURES:
                logger.error(
                    "TTS failing repeatedly (%d times). Check edge-tts binary, "
                    "network connection, and speaker hardware.",
                    self._consecutive_tts_failures,
                )
                # Surface to stderr so `jarvis start` output shows the problem
                print(
                    f"[jarvis] TTS failing repeatedly ({self._consecutive_tts_failures} times): {exc}",
                    flush=True,
                )
        finally:
            media_path.unlink(missing_ok=True)

    def speak(self, text: str) -> None:
        if self._closed:
            return
        self._queue.put(text)

    def is_playing(self) -> bool:
        return self._queue.unfinished_tasks > 0 or self._playing

    def interrupt(self) -> None:
        """Stop any in-progress playback immediately (barge-in, RF-11 off).

        Duck-typed: a playback backend without ``stop`` (e.g. a test fake)
        simply does nothing.
        """
        stop = getattr(self.playback, "stop", None)
        if callable(stop):
            stop()

    def flush(self, timeout: float = 10.0) -> None:
        if self._closed:
            return
        deadline = time.monotonic() + timeout
        while self._queue.unfinished_tasks > 0:
            if time.monotonic() >= deadline:
                return
            time.sleep(0.005)

    def close(self) -> None:
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(None)
        self._thread.join(timeout=5.0)


class MicSwitch:
    """Binds the RF-11 switch to the mic lifecycle.

    Implements the loop's switch_state() callable (True = off). Off releases
    the mic (capturer.stop()) and the wake detector is never consulted while
    off; on resumes capture (capturer.start()).
    """

    def __init__(self, capturer: Capturer, switch_state) -> None:
        self.capturer = capturer
        self._switch = switch_state
        self._off = self._switch()
        if self._off:
            self.capturer.stop()
        else:
            self.capturer.start()

    def __call__(self) -> bool:
        off = self._switch()
        if off != self._off:
            if off:
                self.capturer.stop()
            else:
                self.capturer.start()
            self._off = off
        return off
