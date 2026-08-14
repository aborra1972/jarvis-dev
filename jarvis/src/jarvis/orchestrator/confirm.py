"""Verbal confirmation gate (PR3, task 3.2).

Design ADR-7 / sequence diagram (b): destructive intents (shutdown, reboot,
power_off_self) always ask for spoken confirmation; yes executes, no/timeout
aborts (M6: 100% confirmations, nothing executes without an explicit yes).
The 15s window runs on an injectable Clock so tests exercise yes/no/timeout
without waiting. Response classification is fail-closed: any leading negative
aborts, only an explicit affirmative proceeds.
"""

from __future__ import annotations

from enum import Enum

from jarvis.interpreter.normalize import normalize
from jarvis.interpreter.schema import Intent

CONFIRM_TIMEOUT_S = 15.0
CONFIRM_CANCEL_SPOKEN = "ok, cancelo y no hago nada"
CONFIRM_TIMEOUT_SPOKEN = "no confirmaste a tiempo, cancelé la operación"


class Confirmation(Enum):
    CONFIRMED = "confirmed"
    ABORTED = "aborted"
    TIMED_OUT = "timed_out"


_AFFIRMATIVE: frozenset[str] = frozenset({
    "si", "s", "dale", "dale nomas", "de una", "confirmo", "afirmativo",
    "seguro", "obvio", "ok", "yes", "hacelo", "dalo", "claro",
})
_NEGATIVE: frozenset[str] = frozenset({
    "no", "nop", "nope", "negativo", "para", "cancelalo", "cancela",
    "no hagas nada", "no lo hagas", "nunca", "no se",
})

_PROMPTS: dict[str, str] = {
    "shutdown": "¿Confirmás que apago la máquina?",
    "reboot": "¿Confirmás que reinicio la máquina?",
    "power_off_self": "¿Confirmás que me apago?",
}


def classify_response(text: str) -> Confirmation | None:
    """Classify a spoken answer; ``None`` = unclear, keep listening.

    Fail-closed: leading affirmative → CONFIRMED, leading negative → ABORTED,
    anything else (hesitation, noise) → None so only an explicit answer acts.
    """
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
    return _PROMPTS.get(intent.intent, "¿Confirmás esta operación?")


def confirm(
    intent: Intent,
    *,
    clock,
    capture,
    speaker,
    timeout: float = CONFIRM_TIMEOUT_S,
) -> Confirmation:
    """Ask for verbal confirmation within ``timeout`` seconds (M6)."""
    speaker.speak(confirmation_prompt(intent))
    deadline = clock.now() + timeout
    while True:
        transcript = capture()
        if transcript is not None:
            verdict = classify_response(transcript)
            if verdict is Confirmation.CONFIRMED:
                return Confirmation.CONFIRMED
            if verdict is Confirmation.ABORTED:
                speaker.speak(CONFIRM_CANCEL_SPOKEN)
                return Confirmation.ABORTED
        if clock.now() >= deadline:
            speaker.speak(CONFIRM_TIMEOUT_SPOKEN)
            return Confirmation.TIMED_OUT
