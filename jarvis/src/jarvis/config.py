"""Runtime configuration (bootstrap skeleton).

Wires the repo paths and constants the voice→action bridge needs. Paths default
to the repo's spike artifacts (apply rule: reuse, don't rebuild) and are
resolved relative to this file so the package works from any checkout.
Real usage lands in later PRs: interpreter prompt (PR2), session state (PR3),
executors/allowlists (PR4), voice pipeline (PR5).
"""

from __future__ import annotations

import os
import sys
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

from jarvis.interpreter.schema import build_system_prompt, dangerous_pattern_count  # PR2: real prompt

# --- Layout ------------------------------------------------------------------
_THIS = Path(__file__).resolve()
APP_ROOT = _THIS.parents[2]   # jarvis/ (app root)
REPO_ROOT = _THIS.parents[3]  # repo root (contains spike/)
# Repo-root .env (the same file _load_env() reads). The CLI agent selector
# (``jarvis agent <name>`` / ``jarvis setup``) writes JARVIS_AGENT here so the
# switch persists across runs.
ENV_FILE = REPO_ROOT / ".env"

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
WAKE_THRESHOLD = 0.7  # increased from 0.5 — prevent false activations from noise;
                      # in "name" mode this is the VAD speech-probability gate, not a model score
WAKE_VAD_THRESHOLD = 0.5
# Gate 5.6: the custom XLSR classifier remains available for retraining, but it
# is not production-ready: ambient audio saturates its probability at 1.0.
# Default engine (feature "wake por nombre"): bare-agent-name activation
# ("jarvis, abrí firefox") detected on the VAD speech leading edge with no ML
# model; the loop's name gate verifies the agent name after STT.
WAKE_ENGINE = "name"
WAKE_PREROLL_S = 2.0  # name engine: seconds of pre-roll re-injected so the name reaches the STT
WAKE_XLSR_MODEL = SPIKE / "models" / "jarvis_wake.onnx"
AUDIO_SAMPLE_RATE = 16000
AUDIO_BLOCK_MS = 100
AUDIO_SILENCE_MS = 800
AUDIO_MAX_UTTERANCE_S = 120.0
AUDIO_VAD_THRESHOLD = 0.02
# Silero VAD (T-VAD-01/02): neural voice-activity detector used as the primary
# utterance VAD gate. Falls back to the energy SilenceVAD if the model can't
# load. Set AUDIO_USE_SILERO_VAD=False to force the energy VAD.
AUDIO_USE_SILERO_VAD = True
AUDIO_SILERO_THRESHOLD = 0.5
# Derived VAD selection knobs (single-string form for code that picks the
# VAD by engine name instead of the boolean flag).
VAD_ENGINE = "silero" if AUDIO_USE_SILERO_VAD else "energy"
VAD_SILERO_THRESHOLD = AUDIO_SILERO_THRESHOLD
# Conversation mode (roadmap "sin repetir jarvis en cada comando"): after a
# successfully-executed command, keep listening for this many seconds without
# needing the wake word again. 0 = disabled (always require the wake word).
CONVERSATION_WINDOW_S = 8.0
# Barge-in: while Jarvis is speaking, keep the mic open and let a repeat of
# the wake word interrupt TTS. Off by default — there is no AEC in this
# project, so Jarvis's own voice can false-trigger at the normal threshold.
BARGE_IN_ENABLED = False
BARGE_IN_WAKE_THRESHOLD = 0.85
# Noise-floor calibration (T-CALIB-01): when >0, UtteranceCapture reads this
# many ms of ambient audio right after the wake word and raises the energy VAD
# threshold to noise_floor * AUDIO_CALIBRATE_FACTOR. Set to 0 to disable.
AUDIO_CALIBRATE_MS = 500
AUDIO_CALIBRATE_FACTOR = 1.2
AUDIO_CALIBRATE_MIN_THRESHOLD = 0.01
# Stale-buffer flush (T-FLUSH-01): after TTS playback, drain this many ms of
# queued mic audio so Jarvis's own reply doesn't trigger a false wake word on
# the next cycle. Set to 0 to disable.
AUDIO_FLUSH_MS = 1000
STT_TIMEOUT_S = 15.0
STT_GATE_DURATION_S = 4.0
TTS_TIMEOUT_S = 20.0
PLAY_TIMEOUT_S = 20.0
PLAYER_BIN = "paplay"
# --- Agent / persona selection (jarvis | friday | karen) ----------------------
# Each profile defines the display name, edge-tts voice, the address the agent
# uses to speak to the user, the boot announcement, and the LLM personality
# (system prompt for general QA). Selecting an agent changes name + personality
# + voice across the whole runtime. Switched via JARVIS_AGENT in .env / shell
# env (see cli.py ``agent``/``setup`` which write the repo-root .env).
AGENT_PROFILES: dict[str, dict] = {
    "jarvis": {
        "name": "Jarvis",
        "voice": "en-US-AndrewMultilingualNeural",
        "rate": "-5%",
        "pitch": "-10Hz",
        "address": "señor",
        "announcement": "Buen día, señor. Soy Jarvis, a su servicio.",
        "personality": (
            'Sos Jarvis, un asistente virtual útil y amigable. Tratá al usuario de "señor". '
            "Respondé en español rioplatense, breve y directo. "
            "Máximo 2-3 oraciones. No uses markdown ni formato especial."
        ),
    },
    "friday": {
        "name": "Friday",
        "voice": "en-US-AvaMultilingualNeural",
        "rate": "+5%",
        "pitch": "+0Hz",
        "address": "jefe",
        "announcement": "Buen día, jefe. Soy Friday, a su servicio.",
        "personality": (
            'Sos Friday, la inteligencia artificial de Stark Industries: eficiente, ágil y '
            "directa, con un toque de humor seco. Tratá al usuario de \"jefe\". "
            "Respondé en español rioplatense, breve y directo. "
            "Máximo 2-3 oraciones. No uses markdown ni formato especial."
        ),
    },
    "karen": {
        "name": "Karen",
        "voice": "en-US-EmmaMultilingualNeural",
        "rate": "+3%",
        "pitch": "+5Hz",
        "address": "amigo",
        "announcement": "Buen día, amigo. Soy Karen, a su servicio.",
        "personality": (
            'Sos Karen, la inteligencia artificial del traje de Spider-Man: práctica, directa '
            "y sin vueltas; ayudás con datos concretos y avisos útiles. Tratá al usuario de "
            '"amigo". Respondé en español rioplatense, breve y directo. '
            "Máximo 2-3 oraciones. No uses markdown ni formato especial."
        ),
    },
}


def _resolve_agent_key() -> str:
    """Return the active agent key from ``JARVIS_AGENT``, validated.

    Unknown or invalid values warn on stderr and fall back to ``jarvis`` (the
    project's historical default persona).
    """
    key = os.environ.get("JARVIS_AGENT", "jarvis")
    if key not in AGENT_PROFILES:
        print(
            f"advertencia: JARVIS_AGENT={key!r} no es un agente válido "
            f"({', '.join(sorted(AGENT_PROFILES))}); usando 'jarvis'.",
            file=sys.stderr,
        )
        return "jarvis"
    return key


# Agent selected at import time from env/.env (validated → jarvis fallback).
AGENT: str = _resolve_agent_key()


def active_agent() -> dict:
    """Profile dict of the active agent (re-reads JARVIS_AGENT on each call)."""
    return AGENT_PROFILES[_resolve_agent_key()]


def agent_name() -> str:
    """Display name of the active agent (e.g. "Jarvis", "Friday", "Karen")."""
    return active_agent()["name"]


def agent_voice() -> str:
    """edge-tts voice of the active agent."""
    return active_agent()["voice"]


def agent_rate() -> str:
    """edge-tts speaking rate of the active agent."""
    return active_agent()["rate"]


def agent_pitch() -> str:
    """edge-tts pitch adjustment of the active agent."""
    return active_agent()["pitch"]


def agent_address() -> str:
    """Address the active agent uses for the user (e.g. "señor", "jefe")."""
    return active_agent()["address"]


def agent_personality() -> str:
    """LLM system prompt of the active agent (general QA identity/tono)."""
    return active_agent()["personality"]


def agent_announcement() -> str:
    """Boot announcement of the active agent (spoken on start)."""
    return active_agent()["announcement"]


def set_agent(agent: str) -> Path:
    """Persist ``JARVIS_AGENT=<agent>`` in the repo-root .env.

    Creates the file if missing and preserves every other key/comment line.
    Raises ValueError for unknown agents. Returns the written path.
    """
    if agent not in AGENT_PROFILES:
        raise ValueError(
            f"agente desconocido: {agent!r}; "
            f"válidos: {', '.join(sorted(AGENT_PROFILES))}"
        )
    lines = ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []
    out: list[str] = []
    found = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("JARVIS_AGENT=") or stripped.startswith("export JARVIS_AGENT="):
            out.append(f"JARVIS_AGENT={agent}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"JARVIS_AGENT={agent}")
    ENV_FILE.write_text("\n".join(out) + "\n")
    return ENV_FILE


# TTS engine selection: "edge" = Microsoft neural voices (primary, mp3 via
# gst-launch-1.0), "piper" = offline es_MX-ald-medium fallback (wav via paplay).
TTS_ENGINE = "edge"
# Voice follows the selected agent (EDGE_VOICE = AGENT_PROFILES[AGENT].voice).
# A manual EDGE_VOICE=... in .env/shell still overrides the agent's voice —
# kept for backwards compatibility, but the agent's voice is the intended knob.
EDGE_VOICE: str = os.environ.get("EDGE_VOICE") or AGENT_PROFILES[AGENT]["voice"]
# Voice shaping preserves each persona's pacing and tonal profile after moving
# to multilingual voices. Environment values remain available for fine tuning.
EDGE_RATE: str | None = os.environ.get("EDGE_RATE") or AGENT_PROFILES[AGENT]["rate"]
EDGE_PITCH: str | None = os.environ.get("EDGE_PITCH") or AGENT_PROFILES[AGENT]["pitch"]
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
# Usage-pattern memory: state file for "noticed you did X N times" boot notes
# (usage_patterns.pick_new_suggestion persists here so it never nags every
# single boot with the identical note).
USAGE_SUGGESTIONS_FILE = RUN_DIR / "usage_suggestions.json"
USAGE_PATTERN_MIN_COUNT = 5
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
# 30s covers cold start; subsequent requests are fast (~1-2s).
OLLAMA_TIMEOUT_S: float = 30.0
# Execute mode: False = confirm before any command (Option A), True = auto-execute (Option B)
AUTO_EXECUTE = False
# --- Safety gate (T-SAFE-02): approval layer over AUTO_EXECUTE ---------------
# "auto"   → follow AUTO_EXECUTE; commands matching a dangerous pattern always
#            confirm (AUTO_EXECUTE only skips routine prompts, never risk).
# "strict" → always confirm every `execute` command (default, safest).
# "yolo"   → skip confirmation for routine commands; dangerous commands and
#            destructive intents still confirm (policy beats yolo).
SAFETY_GATE: str = "strict"
# Live count of dangerous command patterns (schema._DANGEROUS_COMMAND_PATTERNS):
# derived from the real table so the documented target never drifts.
DANGEROUS_PATTERNS: int = dangerous_pattern_count()

# --- LLM provider selection (local / gemini / auto) -------------------------
# "local"  = Ollama only (default, offline)
# "gemini" = Google Gemini API only (requires GEMINI_API_KEY)
# "auto"   = Gemini first, fallback to Ollama on failure (best of both)
LLM_PROVIDER: str = os.environ.get("JARVIS_LLM_PROVIDER", "local")
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-3.6-flash"
GEMINI_TIMEOUT_S: float = 5.0
