"""Speech-to-text (PR5, task 5.3).

Design ADR-4: whisper-cli subprocess wrapper (list args, no shell) with
`-l es -bs 1 --prompt <domain>`, 15s timeout, transcript read from stdout
(-np -nt). PR6 (integration): whisper.cpp 1.9.x renames beam size to `-bs`,
and its `--vad` requires an explicit VAD model (`-vm`); without one the flag
makes every invocation fail, so VAD is emitted only when `vad_model` is set —
the app-level SilenceVAD still provides the spec's VAD gate. The q5-medium
decision gate (design gate 5.5) selects the model by estimated utterance
duration: within the gate (<= gate_duration_s, default 4s) the bigger/medium
model is used for accuracy, otherwise the small one for speed. Non-zero exit
surfaces as STTError so the pipeline reports a spoken error.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

STT_TIMEOUT_S = 15.0
GATE_DURATION_S = 4.0
LANGUAGE = "es"


class STTError(Exception):
    """whisper-cli failed or produced no transcript."""


def select_model(
    duration_s: float,
    model_small: Path,
    model_medium: Path | None,
    *,
    gate_duration_s: float = GATE_DURATION_S,
) -> Path:
    """Model gate (design 5.5): medium within the latency gate, else small."""
    if model_medium is not None and duration_s <= gate_duration_s:
        return model_medium
    return model_small


class WhisperSTT:
    def __init__(
        self,
        *,
        whisper_cli: Path,
        model_small: Path,
        model_medium: Path | None = None,
        prompt: str = "",
        language: str = LANGUAGE,
        gate_duration_s: float = GATE_DURATION_S,
        timeout_s: float = STT_TIMEOUT_S,
        beam: int = 1,
        vad_model: Path | None = None,
    ) -> None:
        self.whisper_cli = Path(whisper_cli)
        self.model_small = Path(model_small)
        self.model_medium = Path(model_medium) if model_medium else None
        self.prompt = prompt
        self.language = language
        self.gate_duration_s = gate_duration_s
        self.timeout_s = timeout_s
        self.beam = beam
        self.vad_model = Path(vad_model) if vad_model else None

    def _command(self, wav_path: Path, duration_s: float) -> list[str]:
        model = select_model(
            duration_s, self.model_small, self.model_medium, gate_duration_s=self.gate_duration_s
        )
        cmd = [
            str(self.whisper_cli),
            "-m",
            str(model),
            "-f",
            str(wav_path),
            "-l",
            self.language,
            "-bs",
            str(self.beam),
        ]
        if self.prompt:
            cmd += ["--prompt", self.prompt]
        if self.vad_model is not None:
            cmd += ["--vad", "-vm", str(self.vad_model)]
        cmd += ["-np", "-nt"]
        return cmd

    def transcribe(self, wav_path: Path, duration_s: float) -> str:
        if not Path(wav_path).is_file():
            raise STTError(f"wav not found: {wav_path}")
        cmd = self._command(wav_path, duration_s)
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise STTError(f"whisper-cli failed: {exc}") from exc
        if proc.returncode != 0:
            raise STTError(f"whisper-cli exited {proc.returncode}: {proc.stderr.strip()}")
        transcript = proc.stdout.strip()
        if not transcript:
            raise STTError("whisper-cli produced no transcript")
        return transcript
