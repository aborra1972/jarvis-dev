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
CONFIRM_CANCEL_SPOKEN = "Muy bien, señor. Cancelo y no ejecuto nada."
CONFIRM_TIMEOUT_SPOKEN = "No confirmó a tiempo, señor. He cancelado la operación."


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
    "shutdown": "¿Confirma, señor, que apague la máquina?",
    "reboot": "¿Confirma, señor, que reinicie la máquina?",
    "power_off_self": "¿Confirma, señor, que me apague?",
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
    if intent.intent == "execute":
        cmd = intent.entities.get("command", "desconocido")
        return f"¿Ejecuto el comando: {cmd}, señor?"
    return _PROMPTS.get(intent.intent, "¿Confirma esta operación, señor?")


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
