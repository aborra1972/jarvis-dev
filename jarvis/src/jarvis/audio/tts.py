"""Text-to-speech (PR5, task 5.4; Edge TTS upgrade).

Two engines behind the same interface:
- EdgeTTS (primary): Microsoft neural voice es-MX-JorgeNeural via the edge-tts
  CLI — text on the command line, mp3 written to `--write-media`, 60s timeout
  for long task results (edge-tts chunks long text internally).
- PiperTTS (offline fallback): piper subprocess wrapper for the
  es_MX-ald-medium voice — model and config file passed explicitly, text piped
  via stdin, audio written to `-f wav`, 20s timeout.

Non-zero exit surfaces as TTSError (spec RF-4, latency M2/RNF-1: TTS must not
block the loop).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

TTS_TIMEOUT_S = 20.0
EDGE_TTS_TIMEOUT_S = 60.0


class TTSError(Exception):
    """The TTS engine failed to synthesize the utterance."""


class PiperTTS:
    extension: str = ".wav"

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


class EdgeTTS:
    """Microsoft neural TTS via the edge-tts CLI (primary engine).

    es-MX-JorgeNeural outputs mp3 directly; edge-tts chunks long text
    internally, so the generous timeout covers full task results.
    """

    extension: str = ".mp3"

    def __init__(
        self,
        *,
        bin_path: Path,
        voice: str,
        timeout_s: float = EDGE_TTS_TIMEOUT_S,
        rate: str | None = None,
        pitch: str | None = None,
    ) -> None:
        self.bin_path = Path(bin_path)
        self.voice = voice
        self.timeout_s = timeout_s
        self.rate = rate
        self.pitch = pitch

    def synthesize(self, text: str, out_path: Path) -> Path:
        cmd = [
            str(self.bin_path),
            "--voice",
            self.voice,
            "--text",
            text,
            "--write-media",
            str(out_path),
        ]
        if self.rate:
            cmd += ["--rate", self.rate]
        if self.pitch:
            cmd += ["--pitch", self.pitch]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise TTSError(f"edge-tts failed: {exc}") from exc
        if proc.returncode != 0:
            raise TTSError(f"edge-tts exited {proc.returncode}: {proc.stderr.strip()}")
        if not Path(out_path).is_file():
            raise TTSError("edge-tts did not write the output file")
        return Path(out_path)
