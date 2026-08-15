"""Command interpreter package (PR2).

Public API: :func:`resolve_intent` orchestrates normalize → golden gate → LLM
fallback into an :class:`Interpretation`. The orchestrator (PR3) consumes
this; nothing else in the package is needed outside ``jarvis.interpreter``.
"""

from __future__ import annotations

from jarvis.interpreter.interpreter import Interpretation, resolve_intent

__all__ = ["Interpretation", "resolve_intent"]
