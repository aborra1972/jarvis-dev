"""E2E smoke tests (PR6): real spike binaries, no fakes.

Run explicitly with::

    jarvis/.venv/bin/pytest -m e2e jarvis/tests -q

These tests exercise the REAL stack against the repo's spike artifacts
(whisper.cpp build, piper venv, paplay/PulseAudio, the opencode CLI) and are
excluded from the normal suite via the ``not e2e`` addopts. Every test skips
loudly when a required binary is missing so the suite degrades instead of
failing on machines without the spike build.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from jarvis import config
from jarvis.audio.playback import Playback, PlaybackError
from jarvis.audio.stt import STTError, WhisperSTT
from jarvis.audio.tts import PiperTTS
from jarvis.interpreter.llm import build_opencode_command, parse_assistant_text, parse_session_id

pytestmark = pytest.mark.e2e

SAMPLE_WAV = config.SPIKE / "prueba_orden.wav"


def _skip_missing(binaries: list[Path], label: str) -> None:
    missing = [str(b) for b in binaries if not b.is_file()]
    if missing:
        pytest.skip(f"{label} missing: {', '.join(missing)}")


# --- STT (gate 5.5: measure real small-model latency on the sample) ----------
def test_e2e_whisper_stt_small_timing(capfd) -> None:
    _skip_missing([config.WHISPER_CLI, config.WHISPER_MODEL], "whisper")
    _skip_missing([SAMPLE_WAV], "sample audio")

    stt = WhisperSTT(
        whisper_cli=config.WHISPER_CLI,
        model_small=config.WHISPER_MODEL,
        model_medium=None,
        prompt=config.WHISPER_PROMPT,
        language="es",
        beam=config.WHISPER_BEAM,
        vad_model=None,
    )
    duration_s = 12.0
    started = time.monotonic()
    try:
        transcript = stt.transcribe(SAMPLE_WAV, duration_s)
    except STTError as exc:
        pytest.fail(f"real whisper-cli failed: {exc}")
    elapsed = time.monotonic() - started

    assert transcript.strip(), "real whisper must produce a transcript"
    print(f"\n[e2e] whisper small transcribed {SAMPLE_WAV.name} in {elapsed:.2f}s", flush=True)
    # Gate 5.5 evidence: fp16 medium would exceed the budget and q5-medium is
    # not available in spike, so STT_MEDIUM_PROMOTED stays False (config.py).
    assert config.STT_MEDIUM_PROMOTED is False


# --- TTS + playback (real piper + paplay) -------------------------------------
def test_e2e_piper_tts_and_paplay_playback(tmp_path: Path) -> None:
    _skip_missing([config.PIPER_BIN, config.PIPER_MODEL, config.PIPER_CONFIG], "piper")
    _skip_missing([Path(shutil.which("paplay"))], "paplay") if shutil.which("paplay") else None

    tts = PiperTTS(
        piper_bin=config.PIPER_BIN,
        model=config.PIPER_MODEL,
        config=config.PIPER_CONFIG,
        timeout_s=config.TTS_TIMEOUT_S,
    )
    out = tmp_path / "jarvis-e2e-reply.wav"
    tts.synthesize("hola, soy jarvis", out)
    assert out.is_file() and out.stat().st_size > 1000

    playback = Playback(player="paplay", timeout_s=config.PLAY_TIMEOUT_S)
    try:
        playback.play(out)
    except PlaybackError as exc:
        pytest.fail(f"real paplay failed: {exc}")


# --- opencode: serve + run --attach roundtrip with session binding ------------
def test_e2e_opencode_serve_attach_roundtrip(tmp_path: Path) -> None:
    if shutil.which("opencode") is None:
        pytest.skip("opencode CLI not on PATH")
    repo = config.REPO_ROOT
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    server = subprocess.Popen(
        ["opencode", "serve", "--port", str(port), "--hostname", "127.0.0.1"],
        cwd=str(repo),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_healthy("127.0.0.1", port, timeout=30)
        command = build_opencode_command(url, None, "decime solo: ok", workdir=repo)
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=120
        )
        assert result.returncode == 0, f"opencode run failed: {result.stderr[:200]}"
        text = parse_assistant_text(result.stdout)
        assert text.strip(), "run must return assistant text"
        assert "ok" in text.lower()
        sid = parse_session_id(result.stdout)
        assert sid, "first run must expose a sessionID to bind"
        # Reuse the bound session on a second call.
        reuse = build_opencode_command(url, sid, "decime solo: ok", workdir=repo)
        second = subprocess.run(reuse, capture_output=True, text=True, timeout=120)
        assert second.returncode == 0
        assert parse_assistant_text(second.stdout).strip()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def _wait_healthy(host: str, port: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"opencode serve did not become healthy on {host}:{port}")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
