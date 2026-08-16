"""Audio playback (PR5).

Plays the audio produced by TTS through the system player, picked by file
suffix: wav via paplay (piper) and mp3 via gst-launch-1.0 playbin (edge-tts).
List-args subprocess call, no shell; failures surface as PlaybackError so the
loop can recover on the next iteration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_PLAYER = "paplay"
DEFAULT_MP3_PLAYER = "gst-launch-1.0"
PLAY_TIMEOUT_S = 20.0


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
