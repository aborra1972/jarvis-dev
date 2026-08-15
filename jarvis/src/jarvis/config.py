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
PIPER_BIN = SPIKE / ".venv" / "bin" / "piper"
PIPER_MODEL = SPIKE / "es_AR-daniela-high.onnx"
PIPER_CONFIG = SPIKE / "es_AR-daniela-high.onnx.json"

# --- opencode serve (ADR-1): one headless server per repo --------------------
OPCODE_HOST = "127.0.0.1"
OPCODE_BASE_PORT = 32111

# --- Session state (RF-6): active project + repo→{port, sessionIDs} ----------
STATE_FILE = Path.home() / ".local" / "share" / "jarvis" / "state.json"

# --- Allowlists (executors validate against these; PR4 finalizes) ------------
ALLOWED_APPS: set[str] = {"firefox"}

# --- Interpreter (PR2: JSON-only system prompt built from the schema) --------
INTERPRETER_SYSTEM_PROMPT = build_system_prompt()
