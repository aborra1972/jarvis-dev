"""Golden rule gate (bootstrap skeleton).

Design: deterministic regex gate, authoritative over the LLM, for destructive
intents — shutdown/reboot/power_off_self (spec: golden rejection wins over LLM
suggestion). Real implementation lands in PR2 (interpreter).
"""

from __future__ import annotations


def gate() -> None:
    """Bootstrap stub — real implementation lands in PR2 (interpreter)."""
    raise NotImplementedError("jarvis.interpreter.golden.gate: implemented in PR2 (interpreter)")
