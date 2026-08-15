"""Session/project state (bootstrap skeleton).

Design: active project (git cwd → last known), repo→{port, sessionIDs} map,
re-ask counters, persisted to ~/.local/share/jarvis/state.json (RF-6).
Real implementation lands in PR3 (orchestrator).
"""

from __future__ import annotations


def load_state() -> None:
    """Bootstrap stub — real implementation lands in PR3 (orchestrator)."""
    raise NotImplementedError("jarvis.orchestrator.session.load_state: implemented in PR3 (orchestrator)")
