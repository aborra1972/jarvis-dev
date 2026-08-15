"""Subprocess supervisor policies (bootstrap skeleton).

Design: opencode serve health/restart (3/min backoff), whisper-cli 15s timeout,
piper 20s timeout; failure ⇒ degrade to spoken error (M4). Real implementation
lands in PR3 (orchestrator).
"""

from __future__ import annotations


def supervise() -> None:
    """Bootstrap stub — real implementation lands in PR3 (orchestrator)."""
    raise NotImplementedError("jarvis.orchestrator.supervisor.supervise: implemented in PR3 (orchestrator)")
