"""LLM intent resolution (bootstrap skeleton).

Design: JSON-only intent resolution riding the persistent opencode server
(ADR-2/8) with injectable transport for tests; confidence threshold 0.6 ⇒
re-ask flow (RNF-4). Real implementation lands in PR2 (interpreter).
"""

from __future__ import annotations


def resolve() -> None:
    """Bootstrap stub — real implementation lands in PR2 (interpreter)."""
    raise NotImplementedError("jarvis.interpreter.llm.resolve: implemented in PR2 (interpreter)")
