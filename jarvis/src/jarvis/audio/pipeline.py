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
import tempfile
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


class PiperSpeaker:
    """Synthesizes and plays a spoken reply (contracts.Speaker)."""

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

    def _next_wav(self) -> Path:
        return self.out_dir / f"jarvis-reply-{uuid.uuid4().hex}.wav"

    def speak(self, text: str) -> None:
        wav_path = self._next_wav()
        try:
            wav_path = self.tts.synthesize(text, wav_path)
            self.playback.play(wav_path)
        except (TTSError, PlaybackError):
            pass  # loop keeps running; the human can retry


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
