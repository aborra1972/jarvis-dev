"""Runtime configuration (bootstrap skeleton).

Wires the repo paths and constants the voice→action bridge needs. Paths default
to the repo's spike artifacts (apply rule: reuse, don't rebuild) and are
resolved relative to this file so the package works from any checkout.
Real usage lands in later PRs: interpreter prompt (PR2), session state (PR3),
executors/allowlists (PR4), voice pipeline (PR5).
"""

from __future__ import annotations

from pathlib import Path

from jarvis.interpreter.schema import build_system_prompt  # PR2: real prompt

# --- Layout ------------------------------------------------------------------
_THIS = Path(__file__).resolve()
APP_ROOT = _THIS.parents[2]   # jarvis/ (app root)
REPO_ROOT = _THIS.parents[3]  # repo root (contains spike/)

# --- Subprocess artifacts (reuse spike, do not rebuild) ----------------------
SPIKE = REPO_ROOT / "spike"
WHISPER_CLI = SPIKE / "whisper.cpp" / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_MODEL_MEDIUM = SPIKE / "ggml-medium.bin"
PIPER_BIN = SPIKE / ".venv" / "bin" / "piper"
PIPER_MODEL = SPIKE / "es_AR-daniela-high.onnx"
PIPER_CONFIG = SPIKE / "es_AR-daniela-high.onnx.json"

# --- Voice pipeline (PR5) -----------------------------------------------------
WHISPER_PROMPT = "asistente de desarrollo, comandos de sistema y navegador"
# PR6 integration: whisper.cpp 1.9.x beam size flag is -bs; keep it at 1 (fast).
WHISPER_BEAM = 1
# whisper's own VAD model (silero). None = omit `--vad`; the app-level
# SilenceVAD still provides the spec's VAD gate.
WHISPER_VAD_MODEL: Path | None = None
# PR6 gate 5.5: medium (fp16) exceeds the latency budget and q5-medium is not
# available in spike, so the promote stays OFF until a quantized model lands.
STT_MEDIUM_PROMOTED = False
# PR6 gate 5.6: a trained jarvis.onnx (see docs/wake-word-training.md); None =
# the packaged hey_jarvis_v0.1.onnx.
WAKE_CUSTOM_MODEL: Path | None = None
WAKE_THRESHOLD = 0.5
WAKE_VAD_THRESHOLD = 0.5
AUDIO_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 100
AUDIO_SILENCE_MS = 800
AUDIO_MAX_UTTERANCE_S = 10.0
AUDIO_VAD_THRESHOLD = 0.02
STT_TIMEOUT_S = 15.0
STT_GATE_DURATION_S = 4.0
TTS_TIMEOUT_S = 20.0
PLAY_TIMEOUT_S = 20.0
PLAYER_BIN = "paplay"

# --- opencode serve (ADR-1): one headless server per repo --------------------
OPCODE_HOST = "127.0.0.1"
OPCODE_BASE_PORT = 32111

# --- Session state (RF-6): active project + repo→{port, sessionIDs} ----------
STATE_FILE = Path.home() / ".local" / "share" / "jarvis" / "state.json"

# --- Allowlists (executors validate against these; PR4 finalizes) ------------
ALLOWED_APPS: set[str] = {"firefox"}

# --- Interpreter (PR2: JSON-only system prompt built from the schema) --------
INTERPRETER_SYSTEM_PROMPT = build_system_prompt()
