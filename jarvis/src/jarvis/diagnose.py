"""Pre-start diagnostic: verify all components are ready before launching Jarvis.

Checks microphone, wake word model, whisper CLI + model, Piper (optional),
Ollama server, and audio output. Prints pass/fail with actionable messages.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from jarvis import config


class DiagResult:
    """Single diagnostic check result."""

    def __init__(self, name: str, ok: bool, message: str, hint: str = ""):
        self.name = name
        self.ok = ok
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        icon = "\u2705" if self.ok else "\u274c"
        text = f"{icon} {self.name}: {self.message}"
        if not self.ok and self.hint:
            text += f"\n   -> {self.hint}"
        return text


def _run(cmd: list[str], timeout: float = 5.0) -> Tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -1, "", "timed out"
    except OSError as exc:
        return -1, "", str(exc)


def check_microphone() -> DiagResult:
    """Check that at least one capture device exists."""
    rc, out, err = _run(["arecord", "-l"])
    if rc == 0 and out:
        # Extract first card/device
        lines = out.splitlines()
        device = ""
        for line in lines:
            if line.startswith("card "):
                parts = line.split(":")
                if len(parts) > 1:
                    device = parts[1].strip()
                    break
        return DiagResult(
            "Microfono",
            True,
            device or "dispositivo de captura encontrado",
        )
    hint = "Verifica el microfono: arecord -l"
    if rc == -1:
        hint = "arecord no esta instalado: sudo apt install alsa-utils"
    return DiagResult("Microfono", False, "no se encontro dispositivo", hint)


def check_wake_word() -> DiagResult:
    """Check that the wake word model file exists."""
    if config.WAKE_ENGINE == "openwakeword":
        # openWakeWord uses built-in models, no file check needed
        return DiagResult(
            "Wake word (openWakeWord)",
            True,
            "modelo built-in hey_jarvis disponible",
        )
    model = config.WAKE_CUSTOM_MODEL or config.WAKE_XLSR_MODEL
    if model and model.exists():
        size_mb = model.stat().st_size / (1024 * 1024)
        return DiagResult(
            "Wake word (XLSR)",
            True,
            f"{model.name} ({size_mb:.1f} MB)",
        )
    hint = "Entrena el modelo: segui jarvis/docs/wake-word-training.md"
    return DiagResult(
        "Wake word (XLSR)",
        False,
        f"modelo no encontrado: {model}",
        hint,
    )


def check_whisper() -> DiagResult:
    """Check that whisper-cli and the model file exist."""
    bin_path = config.WHISPER_CLI
    model = config.WHISPER_MODEL_TINY if config.STT_USE_TINY else config.WHISPER_MODEL

    issues = []
    if not bin_path.exists():
        issues.append(f"whisper-cli no encontrado: {bin_path}")
    if not model.exists():
        issues.append(f"modelo no encontrado: {model}")

    if issues:
        hint = "Compila whisper.cpp desde spike/ o descarga el modelo"
        return DiagResult("Whisper", False, "; ".join(issues), hint)

    size_mb = model.stat().st_size / (1024 * 1024)
    return DiagResult(
        "Whisper",
        True,
        f"binario + modelo {model.name} ({size_mb:.0f} MB)",
    )


def check_piper() -> DiagResult:
    """Check Piper TTS (optional fallback)."""
    if config.TTS_ENGINE != "piper":
        return DiagResult(
            "Piper (opcional)",
            True,
            "no requerido (TTS engine = edge)",
        )
    issues = []
    if not config.PIPER_BIN.exists():
        issues.append(f"piper bin no encontrado: {config.PIPER_BIN}")
    if not config.PIPER_MODEL.exists():
        issues.append(f"modelo no encontrado: {config.PIPER_MODEL}")

    if issues:
        return DiagResult(
            "Piper (opcional)",
            False,
            "; ".join(issues),
            "Descarga Piper desde github.com/rhasspy/piper",
        )
    return DiagResult("Piper (opcional)", True, "disponible como fallback")


def check_ollama() -> DiagResult:
    """Check that Ollama server is running and has the model."""
    ollama_bin = shutil.which("ollama") or str(Path.home() / ".local" / "bin" / "ollama")
    rc, out, err = _run([ollama_bin, "list"], timeout=5.0)
    if rc != 0:
        return DiagResult(
            "Ollama",
            False,
            "servidor no corriendo",
            "Inicia el servidor: ollama serve &",
        )
    model = config.INTERPRETER_LLM_MODEL or "qwen2.5:3b"
    if model.lower() in out.lower():
        return DiagResult("Ollama", True, f"modelo {model} disponible")
    return DiagResult(
        "Ollama",
        False,
        f"servidor corre pero modelo '{model}' no esta instalado",
        f"Descarga el modelo: ollama pull {model}",
    )


def check_audio_output() -> DiagResult:
    """Check that audio playback is available."""
    player = config.PLAYER_BIN
    if not shutil.which(player):
        return DiagResult(
            "Audio output",
            False,
            f"{player} no encontrado",
            f"Instala: sudo apt install {player}",
        )
    # Check that pulseaudio/pipewire is running
    rc, out, err = _run(["pactl", "info"], timeout=3.0)
    if rc == 0:
        return DiagResult("Audio output", True, f"{player} + PulseAudio/PipeWire")
    # Fallback: check if aplay works
    rc2, _, _ = _run(["aplay", "-l"], timeout=3.0)
    if rc2 == 0:
        return DiagResult("Audio output", True, f"{player} + ALSA")
    return DiagResult(
        "Audio output",
        False,
        "no se detecto sistema de audio",
        "Reinicia audio: pulseaudio -k && pulseaudio --start",
    )


def run_all() -> list[DiagResult]:
    """Run all diagnostic checks and return results."""
    checks = [
        check_microphone,
        check_wake_word,
        check_whisper,
        check_piper,
        check_ollama,
        check_audio_output,
    ]
    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as exc:
            results.append(
                DiagResult(check.__name__, False, f"error: {exc}", "Revisa el error arriba")
            )
    return results


def main() -> int:
    """Run diagnostics and print results. Returns 0 if all OK, 1 otherwise."""
    print("Diagnosticando componentes de Jarvis...\n")
    results = run_all()
    for r in results:
        print(r)
        print()

    failed = [r for r in results if not r.ok]
    ok_count = len(results) - len(failed)

    print("-" * 50)
    if failed:
        print(f"{ok_count}/{len(results)} componentes OK. {len(failed)} requieren atencion.")
        print("\nCorregi los errores antes de ejecutar 'jarvis start'.")
        return 1
    else:
        print(f"{ok_count}/{len(results)} componentes OK. Todo listo para arrancar!")
        print("\nEjecuta 'jarvis start' para iniciar el asistente.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
