"""Orchestrator loop (PR3, task 3.5).

Drives the FSM from the design sequence diagrams: wake → listen → interpret →
execute / confirm / re-ask×2→reveal / reject → speak → idle, plus the RF-11
switch (off = mic released, wake ignored; non-vocal resume) and
``power_off_self`` → stopped. Everything the loop touches is injected
(Clock, WakeDetector, Capture, Speaker, Executor) so PR4/PR5 slot real
adapters in without rework; tests drive fakes.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from jarvis import config
from jarvis.actions import assistant_lifecycle
from jarvis.orchestrator import usage_patterns
from jarvis.actions.base import build_registry
from jarvis.audio.capture import (
    AudioMetricsPublisher, SilenceVAD, SileroVAD, SoundDeviceCapturer,
    calibrate_noise_floor,
)
from jarvis.audio.pipeline import MicSwitch, PiperSpeaker, UtteranceCapture
from jarvis.audio.playback import Playback
from jarvis.audio.stt import WhisperSTT
from jarvis.audio.tts import EdgeTTS, PiperTTS
from jarvis.audio.wake import build_wake_detector
from jarvis.interpreter import Interpretation, resolve_intent
from jarvis.interpreter.dictation import DictationManager
from jarvis.interpreter.focus import is_code_editor_focused
from jarvis.orchestrator.confirm import (
    CONFIRM_TIMEOUT_S, Authorization, Confirmation, confirm,
)
from jarvis.orchestrator.contracts import CaptureError, OperationToken
from jarvis.audio.contracts import CaptureMode
from jarvis.orchestrator.logs import TranscriptLog, clean_logs
from jarvis.orchestrator.name_gate import strip_agent_prefix
from jarvis.orchestrator.session import GitRunner, Session, load_state
from jarvis.orchestrator.state import Event, State
from jarvis.orchestrator.supervisor import RealClock

logger = logging.getLogger("jarvis.orchestrator")

WAKE_TIMEOUT_S = 30.0
TTS_COOLDOWN_S = 2.0  # increased from 0.5s — prevent wake word detection from TTS audio
MIC_CLOSE_DELAY_S = 0.3  # reduced from 1.5s — close mic quickly after user stops talking


def _init_speaker_verifier():
    """Initialize speaker verifier if enrollment exists."""
    try:
        from jarvis.speaker import get_verifier
        verifier = get_verifier()
        if verifier.is_enrolled():
            return verifier
    except Exception:
        pass
    return None

REASK_1 = "Disculpe, señor, no comprendí. ¿Podría repetir?"
REASK_2 = "Lo lamento, señor, sigo sin comprender. ¿Repite una vez más, por favor?"
REVEAL_PREFIX = "Lo lamento, señor, sigo sin comprender. Esto fue lo que capté: "
REJECTED_SPOKEN = "Eso no es válido, señor. No puedo hacerlo."
UNSUPPORTED_SPOKEN = "Aún no sé hacer eso, señor."
NO_ACTIVE_PROJECT = "No hay un proyecto activo, señor. Abra uno primero."
STT_ERROR_SPOKEN = "Lo lamento, señor, no pude escucharlo. Intente de nuevo."
GOODBYE_SPOKEN = "Hasta luego, señor. Quedo en espera."
# Verify fix (voice-pipeline "Long LLM operation"): spoken ack emitted BEFORE a
# long-running executor call (ask/implement/review/create_artifact can take up
# to 30s). Non-blocking: PiperSpeaker.speak enqueues and returns, so the ack
# plays on the TTS worker while the operation runs.
LONG_OPERATION_ACK = "En ello estoy, señor. Le aviso cuando termine."


def _spoken_toward(default_message: str) -> str:
    """Agent-aware spoken text: swap "señor" for the active agent's address.

    The module-level constants above keep the jarvis defaults (imported
    verbatim by tests); the runtime roads them through this helper so non-jarvis
    agents (friday/karen) address the user with their own treatment. jarvis
    (address == "señor") returns the exact default string.
    """
    address = config.agent_address()
    if address == "señor":
        return default_message
    return default_message.replace("señor", address)


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
    ollama_provider: object | None = None  # for keepalive
    llm_provider: object | None = None  # for fallback notification
    dictation: DictationManager | None = None  # voice-to-text injection
    speaker_verifier: object | None = None  # speaker verification


@dataclass
class _Context:
    transcript: str = ""
    # The loop is the sole owner of active conversation identity.
    active_epoch: int | None = None
    epoch_serial: int = 0
    interpretation: Interpretation | None = None
    outcome: str = ""
    last_spoke_at: float = 0.0  # cooldown: skip wake detection right after TTS
    was_playing: bool = False  # tracks TTS playing state for accurate cooldown
    # Conversation mode (roadmap: "sin repetir jarvis en cada comando"): set
    # after a successfully-executed command to a monotonic deadline; while
    # now() is before it, IDLE skips wake-word detection entirely and goes
    # straight to LISTENING for a follow-up. 0.0 means no active window.
    conversation_until: float = 0.0
    conversation_after_playback: bool = False
    # True when LISTENING was entered from the name-gated wake (engine
    # "name"): the utterance must start with the active agent's name, verified
    # after STT. False for conversation-mode follow-ups and reask retries.
    wake_gated: bool = False
    operation: OperationToken | None = None
    authorization: Authorization | None = None


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
        if state is State.EXECUTING:
            state, context = _tick(state, pipeline, context)
        session.save()
        flush = getattr(pipeline.speaker, "flush", None)
        if callable(flush):
            flush()
    return context.outcome


def _read_wake_threshold(default: float) -> float:
    """Read the GUI-controlled wake threshold without trusting corrupt state."""
    try:
        payload = json.loads(config.STATE_FILE.read_text())
        value = payload.get("wake_threshold", default)
        if isinstance(value, bool):
            return default
        threshold = float(value)
        return threshold if 0.1 <= threshold <= 0.9 else default
    except (AttributeError, FileNotFoundError, OSError, TypeError, ValueError):
        return default


def _sync_wake_threshold(wake: object) -> None:
    if hasattr(wake, "threshold"):
        wake.threshold = _read_wake_threshold(config.WAKE_THRESHOLD)


def _wake_gates_by_name(wake: object) -> bool:
    """True when the wake backend is the name-gated SpeechStartWake."""
    return bool(getattr(wake, "gates_by_name", False))


def _tick(state: State, pipeline: Pipeline, context: _Context) -> tuple[State, _Context]:
    _sync_wake_threshold(pipeline.wake)
    # Process any pending SIGUSR1/SIGUSR2 before checking state.
    # This runs in the main loop (not a signal handler) so I/O is safe.
    _apply_switch(
        pipeline.session, pipeline.switch_state, pipeline.speaker,
        operation=context.operation,
        authorization=context.authorization,
    )
    if _is_switched_off(pipeline):
        if context.active_epoch is not None:
            logger.info("off_precedence")
        context.active_epoch = None
        context.operation = None
        if state is not State.OFF:
            context.outcome = "switched_off"
            return State.OFF, context
    if state is State.IDLE:
        playback_just_finished = False
        if _is_switched_off(pipeline):
            context.outcome = "switched_off"
            return State.OFF, context
        playing = _speaker_is_playing(pipeline.speaker)
        if playing:
            if (
                config.BARGE_IN_ENABLED
                and hasattr(pipeline.wake, 'capturer')
                # Barge-in is inherently broken for VAD speech-start without
                # AEC — Jarvis's own voice would self-interrupt. The name
                # engine keeps the mic STOPPED during playback (else branch).
                and not _wake_gates_by_name(pipeline.wake)
            ):
                # Keep the mic open during playback (instead of stopping it)
                # so a repeated wake word can interrupt Jarvis. No AEC in
                # this project, so we use a stricter threshold than normal
                # wake detection to cut down false triggers from Jarvis's
                # own voice bleeding into the mic — see config.py.
                pipeline.wake.capturer.start()
                original_threshold = getattr(pipeline.wake, "threshold", None)
                try:
                    if original_threshold is not None:
                        pipeline.wake.threshold = config.BARGE_IN_WAKE_THRESHOLD
                    fired = pipeline.wake.wait(0.15)
                finally:
                    if original_threshold is not None:
                        pipeline.wake.threshold = original_threshold
                if fired:
                    interrupt = getattr(pipeline.speaker, "interrupt", None)
                    if callable(interrupt):
                        interrupt()
                    if hasattr(pipeline.wake, 'flush'):
                        pipeline.wake.flush()
                    context.was_playing = False
                    context.last_spoke_at = 0.0
                    context.outcome = "barge_in"
                    try:
                        pipeline.speaker.playback.play_beep()
                    except Exception:
                        pass  # best effort — don't block on beep failure
                    time.sleep(0.2)
                    if hasattr(pipeline.wake, 'flush'):
                        pipeline.wake.flush()
                    if hasattr(pipeline.wake, 'capturer'):
                        pipeline.wake.capturer.start()
                    pipeline.session.reask_attempts = 0
                    _write_fsm_state("listening")
                    context.wake_gated = False  # barge-in is legacy-only now
                    return State.LISTENING, context
            else:
                # PR6 (item 6): never listen over jarvis's own voice.
                # Keep mic stopped while TTS plays to prevent feedback loop.
                if hasattr(pipeline.wake, 'capturer'):
                    pipeline.wake.capturer.stop()
            context.was_playing = True
            if context.authorization is None:
                context.outcome = "speaking"
            return State.IDLE, context
        # TTS just finished — start cooldown from the actual playback end,
        # not from when the FSM entered SPEAKING (which was seconds earlier).
        if context.was_playing:
            context.last_spoke_at = time.monotonic()
            if context.conversation_after_playback and config.CONVERSATION_WINDOW_S > 0:
                context.conversation_until = context.last_spoke_at + config.CONVERSATION_WINDOW_S
                context.conversation_after_playback = False
            context.was_playing = False
            playback_just_finished = True
        # Post-TTS cooldown: wait for speaker hardware to fully stop after
        # the last reply so the mic doesn't capture residual audio.
        if context.last_spoke_at:
            remaining = TTS_COOLDOWN_S - (time.monotonic() - context.last_spoke_at)
            if remaining > 0:
                time.sleep(remaining)
            context.last_spoke_at = 0.0
            # Flush wake detector buffer — discard any TTS audio captured
            # before the mic was restarted.
            if hasattr(pipeline.wake, 'flush'):
                pipeline.wake.flush()
            # T-FLUSH-01: drain the stale mic buffer (Jarvis's own reply
            # audio) too, so it can't trigger a false wake word on the very
            # next cycle. Only after TTS (the mic was open replaying audio).
            if hasattr(pipeline.wake, 'capturer') and hasattr(
                pipeline.wake.capturer, 'flush'
            ):
                pipeline.wake.capturer.flush(ms=config.AUDIO_FLUSH_MS)
            # Restart mic after cooldown
            if hasattr(pipeline.wake, 'capturer'):
                pipeline.wake.capturer.start()
        # Conversation mode: right after a successfully-executed command,
        # skip the wake word for a short follow-up window instead of making
        # the person say "jarvis" again for every single exchange. Expires
        # on its own (config.CONVERSATION_WINDOW_S) so Jarvis doesn't keep
        # listening indefinitely after the conversation is actually over.
        if context.active_epoch is not None:
            if not _prepare_ordinary_capture(pipeline, context):
                return State.IDLE, context
            logger.info("turn.waiting epoch=%s", context.active_epoch)
            _write_fsm_state("listening")
            return State.LISTENING, context
        if (
            not playback_just_finished
            and context.conversation_until
            and time.monotonic() < context.conversation_until
        ):
            context.conversation_until = 0.0
            pipeline.session.reask_attempts = 0
            try:
                pipeline.speaker.playback.play_beep()
            except Exception:
                pass  # best effort — don't block on beep failure
            time.sleep(0.2)
            if hasattr(pipeline.wake, 'flush'):
                pipeline.wake.flush()
            context.outcome = "conversation_continue"
            _write_fsm_state("listening")
            context.wake_gated = False  # follow-up window: no name gate
            return State.LISTENING, context
        if not playback_just_finished:
            context.conversation_until = 0.0
        # Non-TTS returns from LISTENING stop the mic (silence, wrong_speaker,
        # name_mismatch) and nothing else restarted it: ensure the mic is open
        # before the next wake scan. start() is idempotent; flushing the wake
        # buffer discards any stale frames left from the previous cycle.
        if hasattr(pipeline.wake, 'capturer'):
            if hasattr(pipeline.wake, 'flush'):
                pipeline.wake.flush()
            capturer_flush = getattr(pipeline.wake.capturer, 'flush', None)
            if callable(capturer_flush):
                capturer_flush(ms=config.AUDIO_FLUSH_MS)
            pipeline.wake.capturer.start()
        logger.info("wake.waiting timeout=%s", WAKE_TIMEOUT_S)
        wake_fired = pipeline.wake.wait(WAKE_TIMEOUT_S)
        logger.info("wake.result fired=%s", wake_fired)
        if not wake_fired:
            if context.outcome not in ("executed", "failed", "powered_off", "confirmed", "goodbye", "name_mismatch"):
                context.outcome = "no_wake"
            return State.IDLE, context
        pipeline.session.reask_attempts = 0
        context.outcome = "woke"
        # Name-gated wake (engine "name"): the user is mid-utterance ("friday,
        # abrí firefox"). Do NOT stop the mic / beep / sleep — that clips the
        # command. Rewind the pre-roll so the name reaches the STT, then listen.
        if _wake_gates_by_name(pipeline.wake):
            context.epoch_serial += 1
            context.active_epoch = context.epoch_serial
            logger.info("conversation.activated(epoch=%s)", context.active_epoch)
            rewind = getattr(pipeline.wake, "rewind", None)
            if callable(rewind):
                rewind()
            context.wake_gated = True
            _write_fsm_state("listening")
            return State.LISTENING, context
        context.wake_gated = False
        context.epoch_serial += 1
        context.active_epoch = context.epoch_serial
        logger.info("conversation.activated(epoch=%s)", context.active_epoch)
        # Stop mic before beep to prevent capturing our own sound
        if hasattr(pipeline.wake, 'capturer'):
            pipeline.wake.capturer.stop()
        # Play activation beep so user knows Jarvis is listening
        try:
            pipeline.speaker.playback.play_beep()
        except Exception:
            pass  # best effort — don't block on beep failure
        # Wait for beep to fully play and speakers to settle
        time.sleep(0.2)
        # Flush wake detector buffer and restart mic for command capture
        if hasattr(pipeline.wake, 'flush'):
            pipeline.wake.flush()
        if hasattr(pipeline.wake, 'capturer'):
            pipeline.wake.capturer.start()
        _write_fsm_state("listening")
        return State.LISTENING, context

    if state is State.LISTENING:
        if context.active_epoch is not None and _speaker_is_playing(pipeline.speaker):
            logger.info("turn.waiting epoch=%s", context.active_epoch)
            return State.IDLE, context
        if context.operation is None:
            context.operation = OperationToken.next()
        if context.operation.cancelled() or _is_switched_off(pipeline):
            context.outcome = "cancelled"
            return State.OFF if _is_switched_off(pipeline) else State.IDLE, context
        try:
            transcript = _capture(pipeline.capture, context.operation, clock=pipeline.clock.now)
        except CaptureError:
            pipeline.speaker.speak(_spoken_toward(STT_ERROR_SPOKEN))
            context.outcome = "stt_error"
            return (State.SPEAKING if context.active_epoch is not None else State.IDLE), context
        if transcript is None:
            logger.info("capture.result transcript=none")
            context.outcome = "silence"
            return State.IDLE, context
        logger.info("capture.result chars=%d", len(transcript))

        # Name gate: with the "name" wake engine the utterance must start with
        # the active agent's name. Test with what produced the wake — a follow-up
        # in conversation mode (wake_gated False) or a reask retry does not
        # require the name again.
        if context.wake_gated and _wake_gates_by_name(pipeline.wake):
            stripped = strip_agent_prefix(transcript, config.agent_name())
            if stripped is None:
                first_token = transcript.strip().split(maxsplit=1)[0] if transcript.strip() else ""
                logger.info(
                    "name_gate.rejected expected=%s observed_first_token=%r",
                    config.agent_name(), first_token,
                )
                context.active_epoch = None
                context.operation = None
                context.wake_gated = False
                context.outcome = "name_mismatch"
                return State.IDLE, context
            logger.info("name_gate.accepted agent=%s", config.agent_name())
            transcript = stripped

        # --- SPEAKER VERIFICATION ---
        # Check if the voice matches the enrolled speaker
        if pipeline.speaker_verifier is not None and pipeline.speaker_verifier.is_enrolled():
            # Get the audio that was just captured (duck-typed for fakes)
            last_audio_fn = getattr(pipeline.capture, "last_audio", None)
            audio = last_audio_fn() if callable(last_audio_fn) else None
            if audio is not None:
                is_match, similarity = pipeline.speaker_verifier.verify(audio)
                if not is_match:
                    logger.info("Speaker mismatch: similarity=%.3f, ignoring", similarity)
                    context.outcome = "wrong_speaker"
                    return State.IDLE, context

        # Close mic quickly after user finishes speaking to prevent TTS feedback.
        # 0.3s is enough for the user to trail off; keeps mic open just long
        # enough to avoid clipping the tail of the utterance.
        time.sleep(MIC_CLOSE_DELAY_S)
        if hasattr(pipeline.wake, 'capturer'):
            pipeline.wake.capturer.stop()
        # Ack beep DISABLED — visual feedback in GUI is sufficient and avoids

        # --- DICTATION MODE CHECK ---
        # If dictation is active and a code editor is focused, handle dictation
        # instead of normal command processing.
        if pipeline.dictation is not None and pipeline.dictation.is_active:
            should_respond, response_text = pipeline.dictation.process_transcript(transcript)
            if should_respond:
                if response_text == "goodbye":
                    if _is_switched_off(pipeline):
                        context.outcome = "switched_off"
                        return State.OFF, context
                    _close_goodbye(pipeline, context)
                    return State.SPEAKING, context
                pipeline.speaker.speak(response_text)
                _write_fsm_state("speaking")
                context.outcome = "dictation_" + response_text.replace(" ", "_")
                return State.SPEAKING, context
            else:
                # Text was typed into the focused window, continue listening
                context.outcome = "dictated"
                # Don't write FSM state — user is still dictating
                return State.IDLE, context

        # Auto-activate dictation mode if code editor is focused
        # But STILL process the current utterance as a command — only
        # future utterances go to the editor.
        if pipeline.dictation is not None and is_code_editor_focused() and not pipeline.dictation.is_active:
            pipeline.dictation.activate()
            pipeline.speaker.speak("modo dictado activado")
            # Fall through to normal command processing for this utterance

        # --- END DICTATION MODE CHECK ---
        # the 60ms audio delay + speaker hardware latency.
        # To re-enable, uncomment: pipeline.speaker.playback.play_ack_beep()
        _write_fsm_state("thinking", transcript[:50])
        interpretation = pipeline.interpreter(transcript)

        # --- FALLBACK NOTIFICATION ---
        # Check if LLM provider fell back (e.g. Gemini quota → Ollama)
        if pipeline.llm_provider is not None:
            from jarvis.interpreter.llm import FallbackProvider
            if isinstance(pipeline.llm_provider, FallbackProvider):
                if pipeline.llm_provider._fallback_notified:
                    # Notify once, then reset flag
                    pipeline.llm_provider._fallback_notified = False
                    pipeline.speaker.speak(
                        "Señor, se agotaron los créditos de Gemini. "
                        "Estoy usando inteligencia local ahora."
                    )

        context.transcript = transcript
        context.interpretation = interpretation
        if interpretation.control == "goodbye":
            if _is_switched_off(pipeline):
                context.outcome = "switched_off"
                return State.OFF, context
            _close_goodbye(pipeline, context)
            return State.SPEAKING, context
        step = pipeline.session.next_step(interpretation)
        if pipeline.transcript_log is not None:
            pipeline.transcript_log.record(
                transcript,
                intent=interpretation.intent.intent if interpretation.intent else None,
                outcome=step,
                entities=interpretation.intent.entities if interpretation.intent else None,
            )
        if step == "execute":
            context.outcome = "execute"
            intent_name = interpretation.intent.intent if interpretation.intent else ""
            _write_fsm_state("executing", intent_name)
            return State.EXECUTING, context
        if step == "confirm":
            context.outcome = "confirm"
            _write_fsm_state("confirming")
            return State.CONFIRMING, context
        if step == "reask":
            attempt = pipeline.session.reask_attempts
            base_msg = _spoken_toward(REASK_1 if attempt == 1 else REASK_2)
            hint = context.interpretation.suggestion if context.interpretation else None
            pipeline.speaker.speak(f"{base_msg} ¿Quisiste {hint}?" if hint else base_msg)
            context.outcome = "reask"
            context.wake_gated = False  # reask retry: no name gate
            return State.LISTENING, context
        if step == "reveal":
            pipeline.speaker.speak(_spoken_toward(REVEAL_PREFIX) + transcript)
            context.outcome = "revealed"
            return State.SPEAKING, context
        if step == "rejected":
            pipeline.speaker.speak(_spoken_toward(REJECTED_SPOKEN))
            context.outcome = "rejected"
            return State.SPEAKING, context
        if step == "unsupported":
            hint = context.interpretation.suggestion if context.interpretation else None
            pipeline.speaker.speak(
                f"{_spoken_toward(UNSUPPORTED_SPOKEN)} ¿Quisiste {hint}?"
                if hint else _spoken_toward(UNSUPPORTED_SPOKEN)
            )
            context.outcome = "unsupported"
            return State.SPEAKING, context
        context.outcome = "ignore"
        return State.IDLE, context

    if state is State.CONFIRMING:
        intent = context.interpretation.intent
        if context.operation is None:
            context.operation = OperationToken.next()
        if context.operation.cancelled() or _is_switched_off(pipeline):
            context.outcome = "cancelled"
            return State.OFF if _is_switched_off(pipeline) else State.SPEAKING, context
        try:
            verdict = confirm(
                intent,
                clock=pipeline.clock,
                capture=lambda: _capture(
                    pipeline.capture,
                    context.operation,
                    mode=CaptureMode.CONFIRMATION,
                    deadline=(context.authorization.deadline if context.authorization else None),
                    clock=pipeline.clock.now,
                ),
                speaker=pipeline.speaker,
                timeout=pipeline.confirm_timeout,
                authorization=context.authorization,
                token=context.operation,
                authorization_sink=lambda auth: setattr(context, "authorization", auth),
            )
        except CaptureError:
            # PR6 (item 5): a capture failure during the confirmation gate is
            # transient — apologize and retry the confirmation (never abort
            # the destructive op silently).
            pipeline.speaker.speak(_spoken_toward(STT_ERROR_SPOKEN))
            context.outcome = "stt_error"
            return State.CONFIRMING, context
        if verdict is Confirmation.GOODBYE:
            if _is_switched_off(pipeline):
                context.outcome = "switched_off"
                return State.OFF, context
            _close_goodbye(pipeline, context)
            return State.SPEAKING, context
        if verdict is Confirmation.CONFIRMED:
            context.outcome = "confirmed"
            return State.EXECUTING, context
        context.outcome = "aborted" if verdict is Confirmation.ABORTED else "timed_out"
        return State.SPEAKING, context

    if state is State.EXECUTING:
        if context.operation is not None and context.operation.cancelled():
            context.outcome = "cancelled"
            return State.OFF if _is_switched_off(pipeline) else State.SPEAKING, context
        if context.authorization is not None and not context.authorization.consume(
            now=pipeline.clock.now(), token=context.operation
        ):
            pipeline.speaker.speak(_spoken_toward(CONFIRM_TIMEOUT_SPOKEN))
            context.outcome = "timed_out"
            return State.SPEAKING, context
        intent = context.interpretation.intent
        if _needs_repo(intent.intent) and _resolve_repo(pipeline, context) is None:
            pipeline.speaker.speak(_spoken_toward(NO_ACTIVE_PROJECT))
            context.outcome = "rejected"
            _write_fsm_state("speaking")
            return State.SPEAKING, context
        if _is_long_running(pipeline.executor, intent.intent):
            pipeline.speaker.speak(_spoken_toward(LONG_OPERATION_ACK))
        if intent.intent == "general_qa" and config.LLM_PROVIDER == "codex":
            # Codex already returned routing and the optional presentation
            # answer in one envelope; never invoke it again here.
            result = assistant_lifecycle.handle_general_qa(
                intent,
                pipeline.session,
                answer=context.interpretation.answer,
                combined=True,
            )
        elif intent.intent == "general_qa" and config.LLM_PROVIDER not in ("gemini", "codex"):
            # Stream sentence-by-sentence so Jarvis starts speaking before
            # Ollama finishes generating the full answer (see
            # assistant_lifecycle.stream_general_qa). Falls back to the
            # regular blocking path for gemini, since that streaming shape
            # isn't wired up.
            result = assistant_lifecycle.stream_general_qa(
                intent, pipeline.session, pipeline.speaker.speak
            )
        else:
            result = pipeline.executor.execute(intent, pipeline.session)
        streamed_response = result.data.get("response", "")
        history_response = result.spoken or (
            streamed_response if isinstance(streamed_response, str) else ""
        )
        pipeline.session.record_turn(
            context.transcript,
            history_response,
            intent=intent.intent,
            ok=result.ok,
        )
        if result.spoken:
            pipeline.speaker.speak(result.spoken)
        if intent.intent == "power_off_self":
            context.active_epoch = None
            context.outcome = "powered_off"
            return State.STOPPED, context
        context.outcome = "executed" if result.ok else "failed"
        if result.ok and config.CONVERSATION_WINDOW_S > 0:
            context.conversation_after_playback = True
        _write_fsm_state("speaking")
        return State.SPEAKING, context

    if state is State.SPEAKING:
        # Close mic immediately while Jarvis speaks to prevent feedback loop.
        # Cooldown timing is handled by IDLE detecting the playing→finished
        # transition (context.was_playing), not here.
        if hasattr(pipeline.wake, 'capturer'):
            pipeline.wake.capturer.stop()
        _write_fsm_state("idle")
        return State.IDLE, context

    if state is State.OFF:
        if not _is_switched_off(pipeline):
            context.outcome = "resumed"
            return State.IDLE, context
        context.outcome = "off"
        return State.OFF, context

    return State.STOPPED, context


def _close_goodbye(pipeline: Pipeline, context: _Context) -> None:
    """Atomically leave active conversation before emitting its acknowledgement."""
    if context.authorization is not None:
        context.authorization.invalidate("goodbye")
        logger.info("confirmation.invalidated(reason=goodbye)")
    if context.operation is not None:
        context.operation.cancel("goodbye")
    context.authorization = None
    context.operation = None
    context.active_epoch = None
    context.conversation_until = 0.0
    context.conversation_after_playback = False
    context.outcome = "goodbye"
    logger.info("goodbye.accepted(source=voice)")
    _write_fsm_state("idle", "goodbye")
    pipeline.speaker.speak(_spoken_toward(GOODBYE_SPOKEN))


def _prepare_ordinary_capture(pipeline: Pipeline, context: _Context) -> bool:
    """Establish the playback-to-microphone readiness barrier."""
    if context.active_epoch is None or _is_switched_off(pipeline):
        return False
    if _speaker_is_playing(pipeline.speaker):
        return False
    flush = getattr(pipeline.wake, "flush", None)
    if callable(flush):
        flush()
    capturer = getattr(pipeline.wake, "capturer", None)
    if capturer is not None:
        drain = getattr(capturer, "flush", None)
        if callable(drain):
            drain(ms=config.AUDIO_FLUSH_MS)
        start = getattr(capturer, "start", None)
        if callable(start):
            start()
    if _is_switched_off(pipeline):
        logger.info("barrier.failed epoch=%s", context.active_epoch)
        context.active_epoch = None
        return False
    logger.info("barrier.ready epoch=%s", context.active_epoch)
    return True


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
        "review_pr",
        "fix_warnings",
    )


def _resolve_repo(pipeline: Pipeline, context: _Context) -> str | None:
    repo = pipeline.session.resolve_repo(context.interpretation.intent)
    if repo is None:
        return None
    # Explicit switch: only for intents that need project context.
    # open_app uses "app" as the application name, not a project — switching
    # active_project to "firefox" or "chrome" is confusing UX (M7 fix).
    intent_name = context.interpretation.intent.intent
    if "app" in context.interpretation.intent.entities and intent_name != "open_app":
        pipeline.session.switch_active_project(repo)
    pipeline.session.allocate(repo, pipeline.base_port)
    return repo


def _capture(capture: object, operation: OperationToken, *, mode=CaptureMode.ORDINARY, deadline=None, clock=None):
    """Call modern capture adapters while retaining source-compatible fakes."""
    if operation.cancelled():
        return None
    method = getattr(capture, "capture", capture)
    try:
        result = method(mode=mode, deadline=deadline, operation=operation, clock=clock)
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        result = method()
    return None if operation.cancelled() else result


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

ANNOUNCEMENT = config.agent_announcement()


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
    if git_runner is None:
        # RF-6: detect the active project from `git rev-parse --show-toplevel`.
        # This was previously left None here — _git_root() existed but was
        # never wired in, so active-project auto-detection silently never ran
        # outside tests that inject a fake git_runner explicitly.
        git_runner = _git_root
    if wake is None:
        config.LOGS_CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
        config.LOGS_REPLY_DIR.mkdir(parents=True, exist_ok=True)
        capturer = SoundDeviceCapturer(
            sample_rate=config.AUDIO_SAMPLE_RATE,
            block_ms=config.AUDIO_BLOCK_MS,
        )
        # Silero VAD (offline ONNX) by default — much more robust to ambient
        # noise than a fixed RMS threshold. Construction stays side-effect
        # free here (no mic access) so build_pipeline() keeps being safe to
        # call from unit tests; the energy-VAD fallback gets its real
        # noise-floor calibration later, in start(), once the mic is
        # actually running.
        if config.AUDIO_USE_SILERO_VAD:
            vad = SileroVAD(
                threshold=config.AUDIO_SILERO_THRESHOLD,
                sample_rate=config.AUDIO_SAMPLE_RATE,
                block_ms=config.AUDIO_BLOCK_MS,
                silence_s=config.AUDIO_SILENCE_MS / 1000.0,
                max_s=config.AUDIO_MAX_UTTERANCE_S,
            )
        else:
            vad = SilenceVAD(
                threshold=config.AUDIO_VAD_THRESHOLD,
                silence_s=config.AUDIO_SILENCE_MS / 1000.0,
                max_s=config.AUDIO_MAX_UTTERANCE_S,
                sample_rate=config.AUDIO_SAMPLE_RATE,
                block_ms=config.AUDIO_BLOCK_MS,
            )
        stt = WhisperSTT(
            whisper_cli=config.WHISPER_CLI,
            model_small=config.WHISPER_MODEL_TINY if config.STT_USE_TINY else config.WHISPER_MODEL,
            model_medium=config.WHISPER_MODEL_MEDIUM if config.STT_MEDIUM_PROMOTED else None,
            prompt=config.STT_PROMPT,
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
            calibrate_ms=config.AUDIO_CALIBRATE_MS,
            calibrate_factor=config.AUDIO_CALIBRATE_FACTOR,
            calibrate_min_threshold=config.AUDIO_CALIBRATE_MIN_THRESHOLD,
            stop_requested=lambda: _switch_pending is True,
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
        executor = build_registry(speaker=speaker)

    # Wire LLM provider for interpreter (ADR-2: Ollama = Jarvis's brain)
    _ollama = None
    _llm_provider = None
    if interpreter is resolve_intent and config.INTERPRETER_LLM_MODEL:
        from jarvis.interpreter.llm import (
            OllamaProvider, GeminiProvider, CodexProvider, FallbackProvider
        )
        provider_mode = config.LLM_PROVIDER
        _ollama = OllamaProvider(
            model=config.INTERPRETER_LLM_MODEL,
            base_url=config.OLLAMA_BASE_URL,
            timeout=config.OLLAMA_TIMEOUT_S,
        )
        if provider_mode == "codex":
            _provider = CodexProvider(
                workdir=os.getcwd(),
                model=config.CODEX_MODEL,
                timeout=config.CODEX_TIMEOUT_S,
            )
        elif provider_mode == "gemini" and config.GEMINI_API_KEY:
            _provider = GeminiProvider(
                api_key=config.GEMINI_API_KEY,
                model=config.GEMINI_MODEL,
                timeout=config.GEMINI_TIMEOUT_S,
            )
        elif provider_mode == "auto" and config.GEMINI_API_KEY:
            _gemini = GeminiProvider(
                api_key=config.GEMINI_API_KEY,
                model=config.GEMINI_MODEL,
                timeout=config.GEMINI_TIMEOUT_S,
            )
            _provider = FallbackProvider(primary=_gemini, secondary=_ollama)
        else:
            # "local" or gemini without API key → Ollama
            _provider = _ollama
        def _interpret_with_llm(text: str, _prov=_provider) -> Interpretation:
            return resolve_intent(text, provider=_prov)
        interpreter = _interpret_with_llm
        _llm_provider = _provider  # store for fallback notification

    return Pipeline(
        clock=RealClock(),
        wake=wake,
        capture=capture,
        interpreter=interpreter,
        speaker=speaker,
        executor=executor,
        session=session,
        cwd=cwd,
        git_runner=git_runner,
        switch_state=switch_state,
        transcript_log=transcript_log,
        ollama_provider=_ollama if interpreter is not resolve_intent else None,
        llm_provider=_llm_provider if interpreter is not resolve_intent else None,
        dictation=DictationManager(),
        speaker_verifier=_init_speaker_verifier(),
    )


def _ensure_ollama_running() -> None:
    """Start Ollama if not running. Blocks until healthy or timeout."""
    import socket
    import subprocess
    from urllib.parse import urlparse

    parsed = urlparse(config.OLLAMA_BASE_URL)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 11434

    # Quick check: is Ollama already listening?
    try:
        with socket.create_connection((host, port), timeout=2):
            return  # already running
    except OSError:
        pass

    print("[jarvis] Ollama no está corriendo — iniciando...", flush=True)

    # Try to start ollama serve in background
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError:
        print("[jarvis] WARN: 'ollama' no encontrado en PATH — instálalo de https://ollama.com", flush=True)
        return
    except Exception as exc:
        print(f"[jarvis] WARN: no pude iniciar ollama: {exc}", flush=True)
        return

    # Wait up to 15s for Ollama to become healthy
    for _ in range(30):
        time.sleep(0.5)
        try:
            with socket.create_connection((host, port), timeout=2):
                print("[jarvis] Ollama listo ✓", flush=True)
                return
        except OSError:
            continue

    print("[jarvis] WARN: Ollama no respondió en 15s — modo local puede fallar", flush=True)


# --- Ollama keepalive (prevents model unloading) ----------------------------
_KEEPALIVE_INTERVAL_S = 300  # 5 minutes


def _start_ollama_keepalive(pipeline: Pipeline) -> None:
    """Start a background thread that pings Ollama every 5 minutes.

    This prevents Ollama from unloading the model after idle timeout,
    avoiding cold-start latency on the next voice command.
    """
    import threading

    ollama = pipeline.ollama_provider
    if ollama is None or not hasattr(ollama, 'keepalive'):
        return  # no Ollama provider, skip keepalive

    def _keepalive_loop():
        while True:
            time.sleep(_KEEPALIVE_INTERVAL_S)
            try:
                ollama.keepalive()
            except Exception:
                pass  # best-effort — never crash

    thread = threading.Thread(target=_keepalive_loop, daemon=True)
    thread.start()


def _start_audio_metrics_publisher(pipeline: Pipeline) -> AudioMetricsPublisher | None:
    """Start diagnostics only after the runtime has opened its capture path."""
    capturer = getattr(pipeline.wake, "capturer", None)
    metrics = getattr(capturer, "metrics", None)
    if metrics is None:
        return None
    publisher = AudioMetricsPublisher(metrics, config.AUDIO_METRICS_FILE)
    try:
        publisher.start()
    except OSError:
        logger.warning("audio metrics publisher unavailable", exc_info=True)
        return None
    return publisher


def start() -> int:
    """``jarvis start``: run the orchestrator loop with the REAL voice pipeline.

    Announcer readiness through TTS, degrading to a text line if synthesis is
    unavailable. Registers the RF-11 non-vocal switch signals (SIGUSR1 = off,
    SIGUSR2 = on) and publishes a pid file so ``jarvis off``/``jarvis on`` from
    another terminal can signal this process. The loop runs until
    power_off_self (PR6).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(message)s",
        stream=sys.stderr,
    )
    session = load_state(
        str(config.STATE_FILE),
        history_path=str(config.HISTORY_FILE),
    )
    # Ensure Ollama is running before building the LLM pipeline
    provider_mode = config.LLM_PROVIDER
    if provider_mode in ("local", "auto"):
        _ensure_ollama_running()
    pipeline = build_pipeline(session, cwd=os.getcwd())
    # Start Ollama keepalive thread to prevent model unloading
    _start_ollama_keepalive(pipeline)
    _register_switch_signals(session, pipeline.switch_state, pipeline.speaker)
    # SIGTERM: clean exit with state saved. The try/finally in run() saves
    # session and flushes speaker; the outer try/finally removes PID file.
    signal.signal(signal.SIGTERM, lambda *_: (_remove_pid(), sys.exit(0)))
    _write_pid()
    metrics_publisher = None
    try:
        try:
            # Close mic during announcement to prevent feedback
            if hasattr(pipeline.wake, 'capturer'):
                pipeline.wake.capturer.stop()
            pipeline.speaker.speak(ANNOUNCEMENT)
            # Proactive note (no user prompt needed): if the active project
            # has uncommitted changes or unpushed commits, mention it now
            # instead of waiting to be asked. Best-effort — a git failure or
            # missing repo here must never block boot, hence the try/except.
            try:
                repo = _git_root(os.getcwd())
                note = _proactive_project_note(repo) if repo else None
                if note:
                    pipeline.speaker.speak(note)
            except Exception:
                pass
            # "Memoria de patrones de uso": mention a frequently-repeated
            # command once (not every boot — see usage_patterns.pick_new_suggestion).
            try:
                usage_note = usage_patterns.pick_new_suggestion(
                    config.TRANSCRIPTS_FILE,
                    config.USAGE_SUGGESTIONS_FILE,
                    min_count=config.USAGE_PATTERN_MIN_COUNT,
                )
                if usage_note:
                    pipeline.speaker.speak(f"Ah, y {usage_note}, señor.")
            except Exception:
                pass
            pipeline.speaker.flush(timeout=10)
        except Exception:
            print(ANNOUNCEMENT, file=sys.stderr)
        # Allow speaker to fully stop before opening the mic to wake detection.
        time.sleep(3.0)
        # Flush wake detector buffer and restart mic
        if hasattr(pipeline.wake, 'flush'):
            pipeline.wake.flush()
        if hasattr(pipeline.wake, 'capturer'):
            pipeline.wake.capturer.start()
        # Calibrate the energy VAD against this room's real ambient noise now
        # that the mic is actually open. Silero scores speech probability
        # directly and doesn't need this — only the energy fallback does.
        capture_stage = getattr(pipeline, "capture", None)
        vad = getattr(capture_stage, "vad", None)
        if isinstance(vad, SilenceVAD) and hasattr(pipeline.wake, 'capturer'):
            calibrated = calibrate_noise_floor(pipeline.wake.capturer)
            vad.threshold = calibrated
            print(f"[jarvis] piso de ruido calibrado: threshold={calibrated:.4f}", flush=True)
        # Boot readiness handshake with the GUI control panel: it waits for a
        # stdout line containing "listo" to flip "Iniciando..." →
        # "Esperando activación..." (jarvis_gui._read_output), and bosses the
        # same state into the FSM file so a GUI that merely attaches to an
        # existing process (no stdout pipe) still updates via the 2s poll.
        # Provider-agnostic: gemini/Silero boots print nothing else.
        _write_fsm_state("idle")
        print("[jarvis] listo — esperando activación", flush=True)
        metrics_publisher = _start_audio_metrics_publisher(pipeline)
        run(pipeline)
    finally:
        if metrics_publisher is not None:
            metrics_publisher.stop()
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
#
# Signal safety: handlers only set a flag — all I/O and hardware manipulation
# happens in _apply_switch() which runs in the main loop. This prevents
# corrupted state.json from interrupted writes and avoids hardware races.

_switch_pending: bool | None = None  # SIGUSR1→True (off), SIGUSR2→False (on)


def _register_switch_signals(session: Session, switch_state, speaker=None) -> None:
    """Install SIGUSR1 (off) / SIGUSR2 (on) handlers for the running loop.

    The handler only sets a flag; the main loop calls _apply_switch() to
    execute the real work (session save, mic control) safely.
    """

    def _flip(off: bool) -> None:
        global _switch_pending
        _switch_pending = off

    signal.signal(signal.SIGUSR1, lambda *_: _flip(True))
    signal.signal(signal.SIGUSR2, lambda *_: _flip(False))


def _apply_switch(session: Session, switch_state=None, speaker=None, *, operation=None, authorization=None) -> None:
    """Process any pending switch signal in the main loop (safe: no signal context).

    Called at the top of each _tick() to apply SIGUSR1/SIGUSR2 without
    doing I/O or hardware manipulation inside a signal handler.
    """
    global _switch_pending
    if _switch_pending is None:
        return
    off = _switch_pending
    _switch_pending = None

    if off:
        if operation is not None:
            operation.cancel("switch_off")
        if authorization is not None:
            authorization.invalidate("switch_off")
    session.switched_off = off
    session.save()
    if off and speaker is not None:
        # Stop any in-progress TTS playback immediately
        close_fn = getattr(speaker, "close", None)
        if callable(close_fn):
            close_fn()
    if switch_state is not None:
        switch_state()  # MicSwitch: stop/start the mic immediately


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


def _write_fsm_state(state: str, detail: str = "") -> None:
    """Write FSM state to a lightweight file for GUI real-time display.

    Format: ``state:detail`` on a single line (e.g. ``listening:``,
    ``executing:open_app firefox``). The GUI polls this file and maps
    states to labels.
    """
    config.RUN_DIR.mkdir(parents=True, exist_ok=True)
    config.FSM_STATE_FILE.write_text(f"{state}:{detail}")


def _remove_pid() -> None:
    try:
        config.PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    try:
        config.FSM_STATE_FILE.unlink(missing_ok=True)
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


def _proactive_project_note(repo: str) -> str | None:
    """Check the active project for anything worth mentioning unprompted.

    Runs `git status --porcelain` (uncommitted changes) and `git status -sb`
    (ahead of upstream) against the active project. Returns a short spoken
    note, or None if there's nothing notable, git isn't available, or the
    repo path is empty — this must never raise or block boot (best-effort
    only; a broken proactive check should never delay/crash `jarvis start`).
    """
    if not repo:
        return None
    try:
        porcelain = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        branch = subprocess.run(
            ["git", "-C", repo, "status", "-sb"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if porcelain.returncode != 0:
        return None

    notes: list[str] = []
    changed = [line for line in porcelain.stdout.splitlines() if line.strip()]
    if changed:
        word = "archivo" if len(changed) == 1 else "archivos"
        notes.append(f"{len(changed)} {word} sin commitear")
    branch_line = branch.stdout.splitlines()[0] if branch.stdout else ""
    if "ahead" in branch_line:
        notes.append("commits sin subir")

    if not notes:
        return None
    project_name = Path(repo).name
    return f"Ah, señor — en {project_name} tenés {' y '.join(notes)}."
