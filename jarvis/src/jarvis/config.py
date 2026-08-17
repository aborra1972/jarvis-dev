"""Runtime configuration (bootstrap skeleton).

Wires the repo paths and constants the voice→action bridge needs. Paths default
to the repo's spike artifacts (apply rule: reuse, don't rebuild) and are
resolved relative to this file so the package works from any checkout.
Real usage lands in later PRs: interpreter prompt (PR2), session state (PR3),
executors/allowlists (PR4), voice pipeline (PR5).
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_env() -> None:
    """Load .env file from repo root into os.environ (no-op if missing).

    Handles: ``KEY=VALUE``, ``export KEY=VALUE``, ``#`` comments, single/double
    quotes, whitespace. Does not overwrite existing env vars. Intentionally
    does NOT handle multiline values (not needed for API keys).
    """
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip optional 'export ' prefix
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Skip inline comments (e.g. KEY=value  # comment)
        if " " in value:
            value = value.split("#")[0].strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_env()

from jarvis.interpreter.schema import build_system_prompt  # PR2: real prompt

# --- Layout ------------------------------------------------------------------
_THIS = Path(__file__).resolve()
APP_ROOT = _THIS.parents[2]   # jarvis/ (app root)
REPO_ROOT = _THIS.parents[3]  # repo root (contains spike/)

# --- Subprocess artifacts (reuse spike, do not rebuild) ----------------------
SPIKE = REPO_ROOT / "spike"
WHISPER_CLI = SPIKE / "whisper.cpp" / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = SPIKE / "ggml-small.bin"
WHISPER_MODEL_TINY = SPIKE / "ggml-tiny.bin"
WHISPER_MODEL_MEDIUM = SPIKE / "ggml-medium.bin"
PIPER_BIN = SPIKE / ".venv" / "bin" / "piper"
PIPER_MODEL = SPIKE / "es_MX-ald-medium.onnx"
PIPER_CONFIG = SPIKE / "es_MX-ald-medium.onnx.json"
# edge-tts (Microsoft neural voices) ships in the app venv, not the spike venv.
EDGE_TTS_BIN = APP_ROOT / ".venv" / "bin" / "edge-tts"

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
# Use tiny model for faster STT (~2-5x faster than small, ~15% less accurate).
# Good enough for voice commands; download from:
#   wget -P spike/ https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin
STT_USE_TINY = False
# PR6 gate 5.6: a trained jarvis.onnx (see docs/wake-word-training.md); None =
# the packaged hey_jarvis_v0.1.onnx.
WAKE_CUSTOM_MODEL: Path | None = None
WAKE_THRESHOLD = 0.5
WAKE_VAD_THRESHOLD = 0.5
# Gate 5.6: wake word engine selection — "openwakeword" (default) or "xslr"
# (custom wav2vec2-XLSR + LogisticRegression trained on operator voice).
WAKE_ENGINE = "xslr"
WAKE_XLSR_MODEL = SPIKE / "models" / "jarvis_wake.onnx"
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
# TTS engine selection: "edge" = Microsoft neural voices (primary, mp3 via
# gst-launch-1.0), "piper" = offline es_MX-ald-medium fallback (wav via paplay).
TTS_ENGINE = "edge"
EDGE_VOICE = "es-MX-JorgeNeural"
# Optional edge-tts voice shaping flags, e.g. "-10%" or "-5Hz"; None = omit.
EDGE_RATE: str | None = None
EDGE_PITCH: str | None = None
# edge-tts chunks long text internally (~4s per 1000 chars); task results are
# long, so the timeout is generous.
EDGE_TTS_TIMEOUT_S = 60.0

# --- opencode serve (ADR-1): one headless server per repo --------------------
OPCODE_HOST = "127.0.0.1"
OPCODE_BASE_PORT = 32111

# --- Session state (RF-6): active project + repo→{port, sessionIDs} ----------
STATE_FILE = Path.home() / ".local" / "share" / "jarvis" / "state.json"

# --- Runtime dirs (task 6.3): local deletable logs (RNF-3) + signal switch ---
RUN_DIR = Path.home() / ".local" / "state" / "jarvis"
LOGS_DIR = RUN_DIR / "logs"
LOGS_CAPTURE_DIR = LOGS_DIR / "capture"   # utterance wavs (audio logs)
LOGS_REPLY_DIR = LOGS_DIR / "reply"       # TTS reply wavs (audio logs)
TRANSCRIPTS_FILE = LOGS_DIR / "transcripts.jsonl"  # handled transcripts
PID_FILE = RUN_DIR / "jarvis.pid"         # RF-11 non-vocal signal target
FSM_STATE_FILE = RUN_DIR / "fsm_state"    # real-time FSM state for GUI

# --- Allowlists (executors validate against these; PR4 finalizes) ------------
ALLOWED_APPS: set[str] = {
    "firefox",
    "terminal", "gnome-terminal", "nemo", "nautilus", "libreoffice",
    "code", "codium", "vim", "nano", "htop",
    "opencode", "explorador", "spotify",
}

# --- Interpreter (PR2: JSON-only system prompt built from the schema) --------
INTERPRETER_SYSTEM_PROMPT = build_system_prompt()
# LLM provider for intent routing (ADR-2: Ollama = Jarvis's brain)
# None = no LLM (golden gate only); set to an Ollama model name to enable
INTERPRETER_LLM_MODEL: str | None = "qwen2.5:3b"
OLLAMA_BASE_URL = "http://localhost:11434"
# Ollama needs more time than Gemini for first request (model loads into VRAM).
# 15s covers cold start; subsequent requests are fast (~1-2s).
OLLAMA_TIMEOUT_S: float = 15.0
# Execute mode: False = confirm before any command (Option A), True = auto-execute (Option B)
AUTO_EXECUTE = False

# --- LLM provider selection (local / gemini / auto) -------------------------
# "local"  = Ollama only (default, offline)
# "gemini" = Google Gemini API only (requires GEMINI_API_KEY)
# "auto"   = Gemini first, fallback to Ollama on failure (best of both)
LLM_PROVIDER: str = os.environ.get("JARVIS_LLM_PROVIDER", "local")
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-3.6-flash"
GEMINI_TIMEOUT_S: float = 5.0
