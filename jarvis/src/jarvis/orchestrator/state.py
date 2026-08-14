"""Orchestrator FSM (bootstrap skeleton).

Design: idle → listening → confirming → executing → speaking → idle (one of the
5 runtime components, RNF-5). Real implementation lands in PR3 (orchestrator).
"""

from __future__ import annotations


def transition() -> None:
    """Bootstrap stub — real implementation lands in PR3 (orchestrator)."""
    raise NotImplementedError("jarvis.orchestrator.state.transition: implemented in PR3 (orchestrator)")
