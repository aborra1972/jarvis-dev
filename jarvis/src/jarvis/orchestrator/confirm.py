"""Verbal confirmation gate (PR3, task 3.2).

Design ADR-7 / sequence diagram (b): destructive intents (shutdown, reboot,
power_off_self) always ask for spoken confirmation; yes executes, no/timeout
aborts (M6: 100% confirmations, nothing executes without an explicit yes).
The 15s window runs on an injectable Clock so tests exercise yes/no/timeout
without waiting. Response classification is fail-closed: any leading negative
aborts, only an explicit affirmative proceeds.

This PR2 implementation adds the verified-completion authorization seam without
owning loop cancellation orchestration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from jarvis.interpreter.interpreter import is_goodbye
from jarvis.interpreter.normalize import normalize
from jarvis.interpreter.schema import Intent

logger = logging.getLogger("jarvis.orchestrator")

CONFIRM_TIMEOUT_S = 15.0
CONFIRM_CANCEL_SPOKEN = "Muy bien, señor. Cancelo y no ejecuto nada."
CONFIRM_TIMEOUT_SPOKEN = "No confirmó a tiempo, señor. He cancelado la operación."
# Safety multiplier: if the loop runs this many times longer than the nominal
# timeout, something is broken (clock not advancing, capture stuck). Force exit.
_HARD_SAFETY_MULTIPLIER = 3.0


class Confirmation(Enum):
    CONFIRMED = "confirmed"
    ABORTED = "aborted"
    TIMED_OUT = "timed_out"
    GOODBYE = "goodbye"


class AuthorizationState(Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    ABORTED = "aborted"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    CONSUMED = "consumed"


@dataclass
class Authorization:
    """One immutable-from-callers authorization lifecycle.

    The record's deadline can only be established once, from verified prompt
    completion.  ``consume`` is the sole execution handoff and is exactly once.
    """

    action: str
    token: object
    id: str
    state: AuthorizationState = AuthorizationState.PENDING
    t0: float | None = None
    deadline: float | None = None
    reason: str | None = None

    @classmethod
    def create(cls, action: str, token: object) -> "Authorization":
        return cls(action=action, token=token, id=uuid4().hex)

    def verify_prompt_completion(self, completed_at: float) -> bool:
        if self.state is not AuthorizationState.PENDING:
            return False
        self.t0 = completed_at
        self.deadline = completed_at + CONFIRM_TIMEOUT_S
        return True

    def invalidate(self, reason: str = "cancelled") -> bool:
        if self.state in (AuthorizationState.CONSUMED, AuthorizationState.INVALIDATED):
            return False
        self.state = AuthorizationState.INVALIDATED
        self.reason = reason
        return True

    def abort(self, reason: str = "refused") -> bool:
        if self.state is not AuthorizationState.PENDING and self.state is not AuthorizationState.VALIDATED:
            return False
        self.state = AuthorizationState.ABORTED
        self.reason = reason
        return True

    def _live(self, now: float, token: object) -> bool:
        if token != self.token or self.deadline is None:
            return False
        if self.state not in (AuthorizationState.PENDING, AuthorizationState.VALIDATED):
            return False
        if now >= self.deadline:
            self.state = AuthorizationState.EXPIRED
            self.reason = "deadline"
            return False
        return True

    def validate(self, verdict: Confirmation, *, now: float, token: object) -> bool:
        if not self._live(now, token):
            return False
        if verdict is Confirmation.CONFIRMED:
            self.state = AuthorizationState.VALIDATED
            return True
        self.abort("refused")
        return False

    def consume(self, *, now: float, token: object) -> bool:
        """Atomically authorize execution, rejecting late or repeated handoff."""
        if self.state is not AuthorizationState.VALIDATED:
            return False
        if not self._live(now, token):
            return False
        self.state = AuthorizationState.CONSUMED
        return True


_AFFIRMATIVE: frozenset[str] = frozenset({
    "si", "s", "dale", "dale nomas", "de una", "confirmo", "afirmativo",
    "seguro", "obvio", "ok", "yes", "hacelo", "dalo", "claro",
})
_NEGATIVE: frozenset[str] = frozenset({
    "no", "nop", "nope", "negativo", "para", "cancelalo", "cancela",
    "no hagas nada", "no lo hagas", "nunca", "no se",
})
_PROMPTS: dict[str, str] = {
    "shutdown": "¿Confirma, señor, que apague la máquina?",
    "reboot": "¿Confirma, señor, que reinicie la máquina?",
    "power_off_self": "¿Confirma, señor, que me apague?",
}


def classify_response(text: str) -> Confirmation | None:
    surface = normalize(text)
    if not surface:
        return None
    if _starts_with(surface, _AFFIRMATIVE):
        return Confirmation.CONFIRMED
    if _starts_with(surface, _NEGATIVE):
        return Confirmation.ABORTED
    return None


def _starts_with(surface: str, phrases: frozenset[str]) -> bool:
    return surface in phrases or any(surface.startswith(p + " ") for p in phrases)


def confirmation_prompt(intent: Intent) -> str:
    if intent.intent == "execute":
        cmd = intent.entities.get("command", "desconocido")
        return f"¿Ejecuto el comando: {cmd}, señor?"
    return _PROMPTS.get(intent.intent, "¿Confirma esta operación, señor?")


def _prompt_verified(speaker, prompt: str, completion=None) -> bool:
    """Use explicit completion evidence; never use flush or playback state."""
    if completion is not None:
        return bool(getattr(completion, "completed", completion))
    speak_and_wait = getattr(speaker, "speak_and_wait", None)
    if callable(speak_and_wait):
        result = speak_and_wait(prompt)
        return bool(getattr(result, "completed", result))
    # The existing PiperSpeaker's flush is a synchronous queue-drain adapter;
    # retain that source-compatible seam until the loop supplies speak_and_wait.
    # An arbitrary flush-only speaker remains unverified and fails closed.
    if callable(getattr(speaker, "flush", None)):
        speaker.speak(prompt)
        if speaker.__class__.__module__ == "jarvis.audio.pipeline":
            speaker.flush()
            return True
        return False
    # ``speak`` alone provides no evidence that playback completed.
    speaker.speak(prompt)
    return False


def confirm(
    intent: Intent,
    *,
    clock,
    capture,
    speaker,
    timeout: float = CONFIRM_TIMEOUT_S,
    authorization: Authorization | None = None,
    token: object = None,
    prompt_completion=None,
    authorization_sink=None,
) -> Confirmation:
    """Ask for verbal confirmation within the fixed safety window.

    The deadline starts only after explicit prompt-completion evidence. A hard
    safety timeout using real wall-clock time forces exit if an adapter blocks,
    while injected-clock checks remain authoritative for authorization.
    """
    auth = authorization or Authorization.create(intent.intent, token)
    if authorization is None:
        if not _prompt_verified(speaker, confirmation_prompt(intent), prompt_completion):
            auth.invalidate("prompt_completion_unverified")
            return Confirmation.ABORTED
        # Authorization deliberately always uses the fixed safety window.
        auth.verify_prompt_completion(clock.now())
        if authorization_sink is not None:
            authorization_sink(auth)
    elif auth.t0 is None:
        auth.invalidate("prompt_completion_unverified")
        return Confirmation.ABORTED

    hard_deadline = time.monotonic() + (CONFIRM_TIMEOUT_S * _HARD_SAFETY_MULTIPLIER)
    while True:
        if auth.deadline is None or not auth._live(clock.now(), token):
            speaker.speak(CONFIRM_TIMEOUT_SPOKEN)
            return Confirmation.TIMED_OUT
        try:
            transcript = capture()
        except Exception as exc:
            # Preserve the existing loop's recoverable CaptureError seam. Other
            # readiness failures are fail-closed on this authorization record.
            from jarvis.orchestrator.contracts import CaptureError
            if isinstance(exc, CaptureError):
                raise
            logger.warning("capture() failed during confirmation: %s", exc)
            auth.invalidate("capture_failure")
            return Confirmation.ABORTED
        now = clock.now()
        if not auth._live(now, token):
            logger.info("confirmation_late_result", extra={"authorization": auth.id})
            speaker.speak(CONFIRM_TIMEOUT_SPOKEN)
            return Confirmation.TIMED_OUT
        if transcript is not None:
            if is_goodbye(transcript):
                auth.invalidate("goodbye")
                logger.info("confirmation.invalidated(reason=goodbye)")
                return Confirmation.GOODBYE
            verdict = classify_response(transcript)
            if verdict is Confirmation.CONFIRMED:
                if not auth.validate(verdict, now=now, token=token):
                    return Confirmation.ABORTED
                return Confirmation.CONFIRMED
            if verdict is Confirmation.ABORTED:
                auth.abort("refused")
                speaker.speak(CONFIRM_CANCEL_SPOKEN)
                return Confirmation.ABORTED
        if time.monotonic() >= hard_deadline:
            auth.invalidate("safety_timeout")
            speaker.speak(CONFIRM_TIMEOUT_SPOKEN)
            return Confirmation.TIMED_OUT
