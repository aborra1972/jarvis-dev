"""Assistant lifecycle executor (PR4, task 4.7).

Design (binding: single location): power_off_self lives ONLY here and is
golden-gated + 15s-confirmed by the orchestrator; the executor only logs and
acknowledges. handle_help enumerates the 15-command allowlist.
"""

from __future__ import annotations

from jarvis.actions import base
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent
from jarvis.orchestrator.contracts import ActionResult


def power_off_self(intent: Intent, session: object) -> ActionResult:
    base.log("power_off_self")
    return ActionResult(ok=True, spoken="Muy bien, señor. Me apago.")


def handle_help(intent: Intent, session: object) -> ActionResult:
    commands = ", ".join(sorted(ALLOWED_INTENTS - {"unknown"}))
    return ActionResult(ok=True, spoken=f"A su disposición, señor. Puedo: {commands}")
