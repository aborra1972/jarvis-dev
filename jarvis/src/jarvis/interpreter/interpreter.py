"""Interpreter orchestration (PR2, task 2.5): normalize → golden → LLM fallback.

Composes the pure stages into the final Interpretation. Destructive intents
only ever come from the golden hard gate: if the LLM suggests one without a
golden match it is rejected (spec: golden rejection wins over LLM suggestion).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from jarvis import config as _config
from jarvis.interpreter import golden, llm, schema
from jarvis.interpreter.normalize import normalize

# Empty/pointer repo references → delegate the active project to the
# orchestrator (PR3 session state); the interpreter never guesses a path.
ACTIVE_PROJECT_ALIASES: frozenset[str] = frozenset({
    "", "este", "este proyecto", "este repo", "este repositorio",
    "el proyecto", "el repo", "el repositorio", "el proyecto actual",
    "actual", "aca", "aqui", "acá", "aquí",
})


@dataclass
class Interpretation:
    """Final interpreter result; at most one of intent/reask signals applies."""

    intent: schema.Intent | None = None
    needs_reask: bool = False
    rejected_destructive: bool = False
    unsupported: bool = False
    reason: str = ""


def resolve_intent(
    text: str,
    provider: llm.IntentProvider | None = None,
    app_allowlist: set[str] | None = None,
    threshold: float = schema.CONFIDENCE_THRESHOLD,
) -> Interpretation:
    """Resolve a raw transcript to an Interpretation (never emits unvalidated intents)."""
    allowlist = _config.ALLOWED_APPS if app_allowlist is None else app_allowlist

    normalized = normalize(text)
    if not normalized:
        return Interpretation(needs_reask=True, reason="empty")

    # 1. Golden gate FIRST — authoritative for destructive intents (ADR-2).
    hit = golden.gate(normalized)
    if hit is not None:
        if hit.confirm_required:
            return Interpretation(intent=hit)  # destructive: LLM never consulted
        hit = _resolve_active_project(hit)
        invalid = schema.validate_entities(hit, allowlist)
        if invalid:
            return Interpretation(needs_reask=True, reason=f"invalid_entity:{','.join(invalid)}")
        return Interpretation(intent=hit)

    # 2. LLM fallback for everything else (non-destructive).
    if provider is None:
        return Interpretation(needs_reask=True, reason="no_provider")
    try:
        intent = llm.resolve(normalized, schema.build_system_prompt(), provider)
    except schema.SchemaError as exc:
        if exc.code == "unknown_intent":
            return Interpretation(unsupported=True, reason="unknown_intent")
        return Interpretation(needs_reask=True, reason=exc.code)
    except Exception:
        return Interpretation(needs_reask=True, reason="llm_failure")

    intent = replace(intent, source="llm")

    # 3. Hard gate over LLM output: destructive intents without a golden match
    #    are REJECTED (spec: golden rejection wins over LLM suggestion).
    if intent.intent in schema.DESTRUCTIVE_INTENTS:
        return Interpretation(
            needs_reask=True, rejected_destructive=True, reason="golden_rejected_destructive"
        )
    if intent.intent == "unknown":
        return Interpretation(needs_reask=True, reason="unknown")

    intent = _resolve_active_project(intent)
    if intent.confidence < threshold:
        return Interpretation(needs_reask=True, reason="low_confidence")
    invalid = schema.validate_entities(intent, allowlist)
    if invalid:
        return Interpretation(needs_reask=True, reason=f"invalid_entity:{','.join(invalid)}")
    return Interpretation(intent=intent)


def _resolve_active_project(intent: schema.Intent) -> schema.Intent:
    """Delegation: pointer repo references → active project (orchestrator PR3)."""
    if intent.intent == "open_repo" and intent.entities.get("repo", "").strip().lower() in ACTIVE_PROJECT_ALIASES:
        return replace(
            intent, entities={**intent.entities, "repo": ""}, use_active_project=True
        )
    return intent
