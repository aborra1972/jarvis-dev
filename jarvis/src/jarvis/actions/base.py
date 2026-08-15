"""Executor protocol + registry (bootstrap skeleton).

Design: in-process `Executor` protocol `execute(ctx, intent, entities) ->
ActionResult`; executors never receive raw transcripts, only validated
intents+entities. Real implementation lands in PR4 (executors).
"""

from __future__ import annotations


def register() -> None:
    """Bootstrap stub — real implementation lands in PR4 (executors)."""
    raise NotImplementedError("jarvis.actions.base.register: implemented in PR4 (executors)")
