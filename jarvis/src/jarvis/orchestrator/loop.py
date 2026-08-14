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
    voice pipeline yet) the first idle. Persists session state before exit."""
    session = pipeline.session
    session.start(pipeline.cwd, pipeline.git_runner or (lambda cwd: None))
    state = State.IDLE
    context = _Context()
    count = 0
    while state is not State.STOPPED and (iterations is None or count < iterations):
        count += 1
        state, context = _tick(state, pipeline, context)
    session.save()
    return context.outcome


def _tick(state: State, pipeline: Pipeline, context: _Context) -> tuple[State, _Context]:
    if state is State.IDLE:
        if _is_switched_off(pipeline):
            context.outcome = "switched_off"
            return State.OFF, context
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


# --- CLI wiring (task 3.6) ----------------------------------------------------


def start() -> int:
    """``jarvis start``: run the orchestrator loop with PR5-skeleton adapters.

    The orchestrator core (FSM, confirm, re-ask, session) is wired and proven
    end-to-end; the voice pipeline is still a skeleton so a real ``start``
    fails loudly until PR5.
    """
    session = load_state(str(config.STATE_FILE))
    pipeline = Pipeline(
        clock=RealClock(),
        wake=_SkeletonWake(),
        capture=lambda: None,
        interpreter=resolve_intent,
        speaker=_PrintSpeaker(),
        executor=build_registry(),
        session=session,
        cwd=os.getcwd(),
        git_runner=_git_root,
    )
    try:
        run(pipeline, iterations=1)
    except NotImplementedError:
        pass
    print(
        "jarvis start: voice pipeline is still a skeleton (PR5); orchestrator core is wired.",
        file=sys.stderr,
    )
    return 1


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


class _SkeletonWake:
    def wait(self, timeout: float) -> bool:
        return False


class _PrintSpeaker:
    def speak(self, text: str) -> None:
        print(text)


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
