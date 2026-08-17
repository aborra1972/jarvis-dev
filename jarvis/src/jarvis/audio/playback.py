"""Audio playback (PR5).

Plays the audio produced by TTS through the system player, picked by file
suffix: wav via paplay (piper) and mp3 via gst-launch-1.0 playbin (edge-tts).
Also provides a short activation beep for wake-word confirmation.
List-args subprocess call, no shell; failures surface as PlaybackError so the
loop can recover on the next iteration.
"""

from __future__ import annotations

import math
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

DEFAULT_PLAYER = "paplay"
DEFAULT_MP3_PLAYER = "gst-launch-1.0"
PLAY_TIMEOUT_S = 20.0

# Activation beep parameters
_BEEP_FREQ_HZ = 880
_BEEP_DURATION_MS = 150
_BEEP_SAMPLE_RATE = 16000
_BEEP_AMPLITUDE = 0.3

# Ack beep parameters (shorter than activation beep for instant feedback)
_ACK_BEEP_FREQ_HZ = 1200
_ACK_BEEP_DURATION_MS = 60
_ACK_BEEP_AMPLITUDE = 0.2


class PlaybackError(Exception):
    """The player binary failed to play the audio file."""


class Playback:
    def __init__(
        self,
        *,
        player: str = DEFAULT_PLAYER,
        mp3_player: str = DEFAULT_MP3_PLAYER,
        timeout_s: float = PLAY_TIMEOUT_S,
    ) -> None:
        self.player = player
        self.mp3_player = mp3_player
        self.timeout_s = timeout_s

    def play(self, path: Path) -> None:
        if str(path).endswith(".mp3"):
            cmd = [self.mp3_player, "playbin", f"uri=file://{Path(path).resolve()}"]
            player_name = self.mp3_player
        else:
            cmd = [self.player, str(path)]
            player_name = self.player
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise PlaybackError(f"{player_name} failed: {exc}") from exc
        if proc.returncode != 0:
            raise PlaybackError(
                f"{player_name} exited {proc.returncode}: {proc.stderr.strip()}"
            )

    def play_beep(self) -> None:
        """Play a short activation beep to confirm wake-word detection."""
        n_samples = int(_BEEP_SAMPLE_RATE * _BEEP_DURATION_MS / 1000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            beep_path = Path(f.name)
        try:
            with wave.open(str(beep_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(_BEEP_SAMPLE_RATE)
                for i in range(n_samples):
                    t = i / _BEEP_SAMPLE_RATE
                    sample = int(
                        _BEEP_AMPLITUDE * 32767 * math.sin(2 * math.pi * _BEEP_FREQ_HZ * t)
                    )
                    wf.writeframes(struct.pack("<h", sample))
            self.play(beep_path)
            print("[jarvis] beep played", flush=True)
        except Exception as exc:
            print(f"[jarvis] beep failed: {exc}", flush=True)
        finally:
            beep_path.unlink(missing_ok=True)

    def play_ack_beep(self) -> None:
        """Play a very short ack beep to confirm utterance was captured.

        This is shorter and higher-pitched than the activation beep to give
        instant feedback that Jarvis heard the command and is processing it.
        """
        n_samples = int(_BEEP_SAMPLE_RATE * _ACK_BEEP_DURATION_MS / 1000)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            beep_path = Path(f.name)
        try:
            with wave.open(str(beep_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(_BEEP_SAMPLE_RATE)
                for i in range(n_samples):
                    t = i / _BEEP_SAMPLE_RATE
                    sample = int(
                        _ACK_BEEP_AMPLITUDE * 32767 * math.sin(2 * math.pi * _ACK_BEEP_FREQ_HZ * t)
                    )
                    wf.writeframes(struct.pack("<h", sample))
            self.play(beep_path)
        except Exception:
            pass  # ack beep is best-effort, never block
        finally:
            beep_path.unlink(missing_ok=True)
