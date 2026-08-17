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

import os
import queue
import tempfile
import threading
import time
import uuid
from pathlib import Path

from jarvis.audio.capture import SAMPLE_RATE, Capturer, SilenceVAD, gather_utterance, write_wav
from jarvis.audio.playback import PlaybackError
from jarvis.audio.stt import STTError
from jarvis.audio.tts import TTSError
from jarvis.orchestrator.contracts import CaptureError


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
        vad: SilenceVAD,
        *,
        sample_rate: int = SAMPLE_RATE,
        read_timeout: float = 1.0,
        wav_dir: Path | None = None,
    ) -> None:
        self.capturer = capturer
        self.stt = stt
        self.vad = vad
        self.sample_rate = sample_rate
        self.read_timeout = read_timeout
        self.wav_dir = Path(wav_dir) if wav_dir else Path(tempfile.gettempdir())

    def _next_wav(self) -> Path:
        return self.wav_dir / f"jarvis-capture-{uuid.uuid4().hex}.wav"

    def capture(self) -> str | None:
        blocks, duration_s = gather_utterance(
            self.capturer, self.vad, read_timeout=self.read_timeout
        )
        if not blocks or not any(self.vad.is_speech(block) for block in blocks):
            return None
        wav_path = self._next_wav()
        write_wav(wav_path, blocks, sample_rate=self.sample_rate)
        try:
            return self.stt.transcribe(wav_path, duration_s)
        except STTError as exc:
            raise CaptureError(str(exc)) from exc
        finally:
            wav_path.unlink(missing_ok=True)


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
        except (TTSError, PlaybackError):
            pass  # loop keeps running; the human can retry
        finally:
            media_path.unlink(missing_ok=True)

    def speak(self, text: str) -> None:
        if self._closed:
            return
        self._queue.put(text)

    def is_playing(self) -> bool:
        return self._queue.unfinished_tasks > 0 or self._playing

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
