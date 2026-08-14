"""Audio playback (PR5).

Plays the wav produced by piper through the system player (paplay by default,
design Data Flow / TTS output). List-args subprocess call, no shell; failures
surface as PlaybackError so the loop can recover on the next iteration.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

DEFAULT_PLAYER = "paplay"
PLAY_TIMEOUT_S = 20.0


class PlaybackError(Exception):
    """The player binary failed to play the wav."""


class Playback:
    def __init__(
        self,
        *,
        player: str = DEFAULT_PLAYER,
        timeout_s: float = PLAY_TIMEOUT_S,
    ) -> None:
        self.player = player
        self.timeout_s = timeout_s

    def play(self, wav_path: Path) -> None:
        cmd = [self.player, str(wav_path)]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise PlaybackError(f"paplay failed: {exc}") from exc
        if proc.returncode != 0:
            raise PlaybackError(
                f"paplay exited {proc.returncode}: {proc.stderr.strip()}"
            )
