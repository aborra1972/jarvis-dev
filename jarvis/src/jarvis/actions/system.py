"""System executor (bootstrap skeleton).

Design: shutdown/reboot behind the 15s verbal confirm gate, open_app via
xdg-open from an allowlist, no arbitrary shell (RF-8, M4, M6).
Real implementation lands in PR4 (executors).
"""

from __future__ import annotations


def shutdown() -> None:
    """Bootstrap stub — real implementation lands in PR4 (executors)."""
    raise NotImplementedError("jarvis.actions.system.shutdown: implemented in PR4 (executors)")
