"""OpenCode executor (bootstrap skeleton).

Design: persistent headless `serve` lifecycle + `run --attach` with sessionID
reuse (ADR-1), 6 commands (RF-3), health-check/restart/degrade (M4).
Real implementation lands in PR4 (executors).
"""

from __future__ import annotations


def ensure_server() -> None:
    """Bootstrap stub — real implementation lands in PR4 (executors)."""
    raise NotImplementedError("jarvis.actions.opencode.ensure_server: implemented in PR4 (executors)")
