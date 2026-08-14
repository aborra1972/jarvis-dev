"""Assistant lifecycle executor (bootstrap skeleton).

Design: power_off_self lives ONLY here (binding: single location), golden-gated
+ 15s confirm; help; log cleanup (RNF-3). Real implementation lands in PR4
(executors).
"""

from __future__ import annotations


def power_off_self() -> None:
    """Bootstrap stub — real implementation lands in PR4 (executors)."""
    raise NotImplementedError("jarvis.actions.assistant_lifecycle.power_off_self: implemented in PR4 (executors)")
