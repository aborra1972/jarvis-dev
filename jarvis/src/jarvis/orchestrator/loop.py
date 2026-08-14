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
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable

from jarvis import config
from jarvis.actions.base import build_registry
from jarvis.audio.capture import SilenceVAD, SoundDeviceCapturer
from jarvis.audio.pipeline import MicSwitch, PiperSpeaker, UtteranceCapture
from jarvis.audio.playback import Playback
from jarvis.audio.stt import WhisperSTT
from jarvis.audio.tts import PiperTTS
from jarvis.audio.wake import OpenWakeWord
from jarvis.interpreter import Interpretation, resolve_intent
from jarvis.orchestrator.confirm import CONFIRM_TIMEOUT_S, Confirmation, confirm
from jarvis.orchestrator.contracts import CaptureError
from jarvis.orchestrator.session import GitRunner, Session, load_state
from jarvis.orchestrator.state import Event, State
from jarvis.orchestrator.supervisor import RealClock

WAKE_TIMEOUT_S = 30.0

REASK_1 = "no entendí, ¿podés repetir?"
REASK_2 = "no te entiendo, repetí una vez más"
REVEAL_PREFIX = "sigo sin entenderte. esto fue lo que capté: "
REJECTED_SPOKEN = "eso no es válido, no lo puedo hacer"
UNSUPPORTED_SPOKEN = "no sé hacer eso todavía"
NO_ACTIVE_PROJECT = "no tengo un proyecto activo; abrí uno primero"
STT_ERROR_SPOKEN = "no pude escucharte, intentá de nuevo"


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


# --- CLI wiring (task 3.6 / PR6 task 5.7) -------------------------------------

ANNOUNCEMENT = "hola, soy jarvis, listo para ayudarte"


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
) -> Pipeline:
    """Assemble the REAL voice pipeline from config (PR6, task 5.7).

    Defaults construct the real adapters — sounddevice mic, OpenWakeWord,
    whisper-cli STT, piper TTS, paplay playback and the opencode executor
    registry. Every slot can be injected so tests and E2E drive fakes without
    touching hardware; defaults are only exercised by ``start``/``e2e``.
    """
    if wake is None:
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
        capture = UtteranceCapture(capturer, stt, vad, sample_rate=config.AUDIO_SAMPLE_RATE)
        wake = OpenWakeWord(
            capturer,
            threshold=config.WAKE_THRESHOLD,
            vad_threshold=config.WAKE_VAD_THRESHOLD,
            custom=config.WAKE_CUSTOM_MODEL,
        )
        if switch_state is None:
            switch_state = MicSwitch(capturer, lambda: session.switched_off)
    if speaker is None:
        tts = PiperTTS(
            piper_bin=config.PIPER_BIN,
            model=config.PIPER_MODEL,
            config=config.PIPER_CONFIG,
            timeout_s=config.TTS_TIMEOUT_S,
        )
        playback = Playback(player=config.PLAYER_BIN, timeout_s=config.PLAY_TIMEOUT_S)
        speaker = PiperSpeaker(tts, playback)
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
    )


def start() -> int:
    """``jarvis start``: run the orchestrator loop with the REAL voice pipeline.

    Announcer readiness through TTS, degrading to a text line if synthesis is
    unavailable. The loop runs until power_off_self (PR6).
    """
    session = load_state(str(config.STATE_FILE))
    pipeline = build_pipeline(session, cwd=os.getcwd())
    try:
        pipeline.speaker.speak(ANNOUNCEMENT)
    except Exception:
        print(ANNOUNCEMENT, file=sys.stderr)
    run(pipeline)
    return 0


def switch_off() -> int:
    """``jarvis off`` (RF-11): release the mic, ignore wake until ``on``."""
    session = load_state(str(config.STATE_FILE))
    session.switched_off = True
    session.save()
    print("jarvis off: mic released, no listening until `jarvis on`", file=sys.stderr)
    return 0


def switch_on() -> int:
    """``jarvis on`` (RF-11): resume listening."""
    session = load_state(str(config.STATE_FILE))
    session.switched_off = False
    session.save()
    print("jarvis on: listening resumed", file=sys.stderr)
    return 0


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
