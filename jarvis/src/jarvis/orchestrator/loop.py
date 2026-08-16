"""Orchestrator loop (PR3, task 3.5).

Drives the FSM from the design sequence diagrams: wake → listen → interpret →
execute / confirm / re-ask×2→reveal / reject → speak → idle, plus the RF-11
switch (off = mic released, wake ignored; non-vocal resume) and
``power_off_self`` → stopped. Everything the loop touches is injected
(Clock, WakeDetector, Capture, Speaker, Executor) so PR4/PR5 slot real
adapters in without rework; tests drive fakes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from jarvis import config
from jarvis.actions.base import build_registry
from jarvis.audio.capture import SilenceVAD, SoundDeviceCapturer
from jarvis.audio.pipeline import MicSwitch, PiperSpeaker, UtteranceCapture
from jarvis.audio.playback import Playback
from jarvis.audio.stt import WhisperSTT
from jarvis.audio.tts import EdgeTTS, PiperTTS
from jarvis.audio.wake import build_wake_detector
from jarvis.interpreter import Interpretation, resolve_intent
from jarvis.orchestrator.confirm import CONFIRM_TIMEOUT_S, Confirmation, confirm
from jarvis.orchestrator.contracts import CaptureError
from jarvis.orchestrator.logs import TranscriptLog, clean_logs
from jarvis.orchestrator.session import GitRunner, Session, load_state
from jarvis.orchestrator.state import Event, State
from jarvis.orchestrator.supervisor import RealClock

WAKE_TIMEOUT_S = 30.0

REASK_1 = "Disculpe, señor, no comprendí. ¿Podría repetir?"
REASK_2 = "Lo lamento, señor, sigo sin comprender. ¿Repite una vez más, por favor?"
REVEAL_PREFIX = "Lo lamento, señor, sigo sin comprender. Esto fue lo que capté: "
REJECTED_SPOKEN = "Eso no es válido, señor. No puedo hacerlo."
UNSUPPORTED_SPOKEN = "Aún no sé hacer eso, señor."
NO_ACTIVE_PROJECT = "No hay un proyecto activo, señor. Abra uno primero."
STT_ERROR_SPOKEN = "Lo lamento, señor, no pude escucharlo. Intente de nuevo."
# Verify fix (voice-pipeline "Long LLM operation"): spoken ack emitted BEFORE a
# long-running executor call (ask/implement/review/create_artifact can take up
# to 30s). Non-blocking: PiperSpeaker.speak enqueues and returns, so the ack
# plays on the TTS worker while the operation runs.
LONG_OPERATION_ACK = "En ello estoy, señor. Le aviso cuando termine."


@dataclass
class Pipeline:
    clock: object
    wake: object
    capture: Callable[[], str | None]
    interpreter: Callable[[str], Interpretation]
    speaker: object
    executor: object
    session: Session
    cwd: str = ""
    git_runner: GitRunner | None = None
    confirm_timeout: float = CONFIRM_TIMEOUT_S
    base_port: int = config.OPCODE_BASE_PORT
    switch_state: Callable[[], bool] | None = None
    transcript_log: object | None = None


@dataclass
class _Context:
    transcript: str = ""
    interpretation: Interpretation | None = None
    outcome: str = ""


def run(pipeline: Pipeline, *, iterations: int | None = None) -> str:
    """Run the FSM loop until stopped, iterations are exhausted, or (with no
    voice pipeline yet) the first idle. Persists session state and flushes any
    pending spoken reply before exit."""
    session = pipeline.session
    session.start(pipeline.cwd, pipeline.git_runner or (lambda cwd: None))
    state = State.IDLE
    context = _Context()
    count = 0
    try:
        while state is not State.STOPPED and (iterations is None or count < iterations):
            count += 1
            state, context = _tick(state, pipeline, context)
    finally:
        session.save()
        flush = getattr(pipeline.speaker, "flush", None)
        if callable(flush):
            flush()
    return context.outcome


def _tick(state: State, pipeline: Pipeline, context: _Context) -> tuple[State, _Context]:
    if state is State.IDLE:
        if _is_switched_off(pipeline):
            context.outcome = "switched_off"
            return State.OFF, context
        if _speaker_is_playing(pipeline.speaker):
            # PR6 (item 6): never listen over jarvis's own voice.
            context.outcome = "speaking"
            return State.IDLE, context
        if not pipeline.wake.wait(WAKE_TIMEOUT_S):
            context.outcome = "no_wake"
            return State.IDLE, context
        pipeline.session.reask_attempts = 0
        context.outcome = "woke"
        return State.LISTENING, context

    if state is State.LISTENING:
        try:
            transcript = pipeline.capture.capture()
        except CaptureError:
            pipeline.speaker.speak(STT_ERROR_SPOKEN)
            context.outcome = "stt_error"
            return State.IDLE, context
        if transcript is None:
            context.outcome = "silence"
            return State.IDLE, context
        interpretation = pipeline.interpreter(transcript)
        context.transcript = transcript
        context.interpretation = interpretation
        step = pipeline.session.next_step(interpretation)
        if pipeline.transcript_log is not None:
            pipeline.transcript_log.record(
                transcript,
                intent=interpretation.intent.intent if interpretation.intent else None,
                outcome=step,
            )
        if step == "execute":
            context.outcome = "execute"
            return State.EXECUTING, context
        if step == "confirm":
            context.outcome = "confirm"
            return State.CONFIRMING, context
        if step == "reask":
            attempt = pipeline.session.reask_attempts
            pipeline.speaker.speak(REASK_1 if attempt == 1 else REASK_2)
            context.outcome = "reask"
            return State.LISTENING, context
        if step == "reveal":
            pipeline.speaker.speak(REVEAL_PREFIX + transcript)
            context.outcome = "revealed"
            return State.SPEAKING, context
        if step == "rejected":
            pipeline.speaker.speak(REJECTED_SPOKEN)
            context.outcome = "rejected"
            return State.SPEAKING, context
        if step == "unsupported":
            pipeline.speaker.speak(UNSUPPORTED_SPOKEN)
            context.outcome = "unsupported"
            return State.SPEAKING, context
        context.outcome = "ignore"
        return State.IDLE, context

    if state is State.CONFIRMING:
        intent = context.interpretation.intent
        try:
            verdict = confirm(
                intent,
                clock=pipeline.clock,
                capture=pipeline.capture.capture,
                speaker=pipeline.speaker,
                timeout=pipeline.confirm_timeout,
            )
        except CaptureError:
            # PR6 (item 5): a capture failure during the confirmation gate is
            # transient — apologize and retry the confirmation (never abort
            # the destructive op silently).
            pipeline.speaker.speak(STT_ERROR_SPOKEN)
            context.outcome = "stt_error"
            return State.CONFIRMING, context
        if verdict is Confirmation.CONFIRMED:
            context.outcome = "confirmed"
            return State.EXECUTING, context
        context.outcome = "aborted" if verdict is Confirmation.ABORTED else "timed_out"
        return State.SPEAKING, context

    if state is State.EXECUTING:
        intent = context.interpretation.intent
        if _needs_repo(intent.intent) and _resolve_repo(pipeline, context) is None:
            pipeline.speaker.speak(NO_ACTIVE_PROJECT)
            context.outcome = "rejected"
            return State.SPEAKING, context
        if _is_long_running(pipeline.executor, intent.intent):
            pipeline.speaker.speak(LONG_OPERATION_ACK)
        result = pipeline.executor.execute(intent, pipeline.session)
        pipeline.speaker.speak(result.spoken)
        if intent.intent == "power_off_self":
            context.outcome = "powered_off"
            return State.STOPPED, context
        context.outcome = "executed" if result.ok else "failed"
        return State.SPEAKING, context

    if state is State.SPEAKING:
        return State.IDLE, context

    if state is State.OFF:
        if not _is_switched_off(pipeline):
            context.outcome = "resumed"
            return State.IDLE, context
        context.outcome = "off"
        return State.OFF, context

    return State.STOPPED, context


def _needs_repo(intent: str) -> bool:
    # open_repo deliberately excluded: the executor owns project switching
    # (switch + allocate), so an explicit repo works even without an active
    # project (PR4).
    return intent in (
        "open_app",
        "open_url",
        "ask",
        "configure",
        "create_artifact",
        "implement",
        "review",
    )


def _resolve_repo(pipeline: Pipeline, context: _Context) -> str | None:
    repo = pipeline.session.resolve_repo(context.interpretation.intent)
    if repo is None:
        return None
    pipeline.session.allocate(repo, pipeline.base_port)
    return repo


def _is_switched_off(pipeline: Pipeline) -> bool:
    if pipeline.switch_state is not None:
        return pipeline.switch_state()
    return pipeline.session.switched_off


def _speaker_is_playing(speaker: object) -> bool:
    is_playing = getattr(speaker, "is_playing", None)
    return bool(is_playing()) if callable(is_playing) else False


def _is_long_running(executor: object, intent: str) -> bool:
    """True when the executor flags this intent as >3s (ack before it runs).

    Duck-typed so bare fakes without the attribute answer False (no ack).
    """
    long_running = getattr(executor, "long_running_intents", frozenset())
    return intent in long_running


# --- CLI wiring (task 3.6 / PR6 task 5.7) -------------------------------------

ANNOUNCEMENT = "Buen día, señor. Soy Jarvis, a su servicio."


def build_pipeline(
    session: Session,
    *,
    cwd: str,
    wake: object | None = None,
    capture: object | None = None,
    speaker: object | None = None,
    interpreter: Callable[[str], Interpretation] = resolve_intent,
    executor: object | None = None,
    git_runner: GitRunner | None = None,
    switch_state: Callable[[], bool] | None = None,
    transcript_log: object | None = None,
) -> Pipeline:
    """Assemble the REAL voice pipeline from config (PR6, task 5.7).

    Defaults construct the real adapters — sounddevice mic, OpenWakeWord,
    whisper-cli STT, piper TTS, paplay playback and the opencode executor
    registry. Every slot can be injected so tests and E2E drive fakes without
    touching hardware; defaults are only exercised by ``start``/``e2e``.
    Transcripts and audio logs land under config.LOGS_DIR (task 6.3, RNF-3).
    """
    if transcript_log is None:
        transcript_log = TranscriptLog(config.TRANSCRIPTS_FILE)
    if wake is None:
        config.LOGS_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        config.LOGS_REPLY_DIR.mkdir(parents=True, exist_ok=True)
        capturer = SoundDeviceCapturer(
            sample_rate=config.AUDIO_SAMPLE_RATE,
            block_ms=config.AUDIO_BLOCK_MS,
        )
        vad = SilenceVAD(
            threshold=config.AUDIO_VAD_THRESHOLD,
            silence_s=config.AUDIO_SILENCE_MS / 1000.0,
            max_s=config.AUDIO_MAX_UTTERANCE_S,
            sample_rate=config.AUDIO_SAMPLE_RATE,
            block_ms=config.AUDIO_BLOCK_MS,
        )
        stt = WhisperSTT(
            whisper_cli=config.WHISPER_CLI,
            model_small=config.WHISPER_MODEL,
            model_medium=config.WHISPER_MODEL_MEDIUM if config.STT_MEDIUM_PROMOTED else None,
            prompt=config.WHISPER_PROMPT,
            language="es",
            gate_duration_s=config.STT_GATE_DURATION_S,
            timeout_s=config.STT_TIMEOUT_S,
            beam=config.WHISPER_BEAM,
            vad_model=config.WHISPER_VAD_MODEL,
        )
        capture = UtteranceCapture(
            capturer,
            stt,
            vad,
            sample_rate=config.AUDIO_SAMPLE_RATE,
            wav_dir=config.LOGS_CAPTURE_DIR,
        )
        wake = build_wake_detector(
            capturer,
            engine=config.WAKE_ENGINE,
            classifier_path=config.WAKE_XLSR_MODEL if config.WAKE_ENGINE == "xslr" else None,
            threshold=config.WAKE_THRESHOLD,
        )
        if switch_state is None:
            switch_state = MicSwitch(capturer, lambda: session.switched_off)
    if speaker is None:
        if config.TTS_ENGINE == "edge":
            tts = EdgeTTS(
                bin_path=config.EDGE_TTS_BIN,
                voice=config.EDGE_VOICE,
                timeout_s=config.EDGE_TTS_TIMEOUT_S,
                rate=config.EDGE_RATE,
                pitch=config.EDGE_PITCH,
            )
        else:  # "piper" offline fallback
            tts = PiperTTS(
                piper_bin=config.PIPER_BIN,
                model=config.PIPER_MODEL,
                config=config.PIPER_CONFIG,
                timeout_s=config.TTS_TIMEOUT_S,
            )
        playback = Playback(player=config.PLAYER_BIN, timeout_s=config.PLAY_TIMEOUT_S)
        speaker = PiperSpeaker(tts, playback, out_dir=config.LOGS_REPLY_DIR)
    if executor is None:
        executor = build_registry()
    return Pipeline(
        clock=RealClock(),
        wake=wake,
        capture=capture,
        interpreter=interpreter,
        speaker=speaker,
        executor=executor,
        session=session,
        cwd=cwd,
        git_runner=git_runner or _git_root,
        base_port=config.OPCODE_BASE_PORT,
        switch_state=switch_state,
        transcript_log=transcript_log,
    )


def start() -> int:
    """``jarvis start``: run the orchestrator loop with the REAL voice pipeline.

    Announcer readiness through TTS, degrading to a text line if synthesis is
    unavailable. Registers the RF-11 non-vocal switch signals (SIGUSR1 = off,
    SIGUSR2 = on) and publishes a pid file so ``jarvis off``/``jarvis on`` from
    another terminal can signal this process. The loop runs until
    power_off_self (PR6).
    """
    session = load_state(str(config.STATE_FILE))
    pipeline = build_pipeline(session, cwd=os.getcwd())
    _register_switch_signals(session, pipeline.switch_state)
    _write_pid()
    try:
        try:
            pipeline.speaker.speak(ANNOUNCEMENT)
        except Exception:
            print(ANNOUNCEMENT, file=sys.stderr)
        run(pipeline)
    finally:
        _remove_pid()
    return 0


def switch_off() -> int:
    """``jarvis off`` (RF-11): release the mic, ignore wake until ``on``."""
    session = load_state(str(config.STATE_FILE))
    session.switched_off = True
    session.save()
    _signal_running(signal.SIGUSR1)
    print("jarvis off: mic released, no listening until `jarvis on`", file=sys.stderr)
    return 0


def switch_on() -> int:
    """``jarvis on`` (RF-11): resume listening."""
    session = load_state(str(config.STATE_FILE))
    session.switched_off = False
    session.save()
    _signal_running(signal.SIGUSR2)
    print("jarvis on: listening resumed", file=sys.stderr)
    return 0


def clean() -> int:
    """``jarvis clean``: delete local transcripts and audio (RNF-3), confirm.

    Preserves state.json — the RF-6 session and the RF-11 off switch are
    context, not logs. Confirmation is printed as text (clean is a CLI command;
    the spec's spoken+text confirmation applies when the assistant says it).
    """
    deleted = clean_logs(config.LOGS_DIR)
    message = (
        f"jarvis clean: {deleted} archivo(s) de log eliminados"
        if deleted
        else "jarvis clean: no había logs que borrar"
    )
    print(message, file=sys.stderr)
    return 0


# --- RF-11 non-vocal switch: signal-based (task 6.3) --------------------------
# The FSM keeps the loop OFF without touching the mic/wake (design sequence
# diagram d); these handlers make the switch cross-process. `jarvis off`/`on`
# persist state.json AND signal the running loop (SIGUSR1/SIGUSR2); a spoken
# wake word can never reactivate it because no mic is open while OFF.

def _register_switch_signals(session: Session, switch_state) -> None:
    """Install SIGUSR1 (off) / SIGUSR2 (on) handlers for the running loop."""

    def _flip(off: bool) -> None:
        session.switched_off = off
        session.save()
        if switch_state is not None:
            switch_state()  # MicSwitch: stop/start the mic immediately

    signal.signal(signal.SIGUSR1, lambda *_: _flip(True))
    signal.signal(signal.SIGUSR2, lambda *_: _flip(False))


def _signal_running(sig: int, pid_file: Path | None = None) -> None:
    """Signal a live loop process (no-op when none is running)."""
    path = pid_file or config.PID_FILE
    try:
        pid = int(path.read_text().strip())
    except (FileNotFoundError, OSError, ValueError):
        return
    try:
        os.kill(pid, sig)
    except ProcessLookupError:
        try:
            path.unlink()
        except OSError:
            pass
    except OSError:
        pass


def _write_pid() -> None:
    config.RUN_DIR.mkdir(parents=True, exist_ok=True)
    config.PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    try:
        config.PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _git_root(cwd: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return root or None
