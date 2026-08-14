"""Text-to-speech (PR5, task 5.4).

Design ADR-5: piper subprocess wrapper for the es_AR-daniela voice — model and
config file passed explicitly, text piped via stdin, audio written to `-f
wav`, 20s timeout. Non-zero exit surfaces as TTSError (spec RF-4, latency
M2/RNF-1: piper must not block the loop).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TTS_TIMEOUT_S = 20.0


class TTSError(Exception):
    """piper failed to synthesize the utterance."""


class PiperTTS:
    def __init__(
        self,
        *,
        piper_bin: Path,
        model: Path,
        config: Path,
        timeout_s: float = TTS_TIMEOUT_S,
    ) -> None:
        self.piper_bin = Path(piper_bin)
        self.model = Path(model)
        self.config = Path(config)
        self.timeout_s = timeout_s

    def synthesize(self, text: str, out_path: Path) -> Path:
        cmd = [
            str(self.piper_bin),
            "-m",
            str(self.model),
            "-c",
            str(self.config),
            "-f",
            str(out_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise TTSError(f"piper failed: {exc}") from exc
        if proc.returncode != 0:
            raise TTSError(f"piper exited {proc.returncode}: {proc.stderr.strip()}")
        return Path(out_path)
