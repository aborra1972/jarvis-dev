"""Verbal confirmation gate (bootstrap skeleton).

Design: 15s confirm with injectable clock for shutdown/reboot/power_off_self;
yes proceeds, no/timeout aborts (M6, 100% confirmations). Real implementation
lands in PR3 (orchestrator).
"""

from __future__ import annotations


def confirm() -> None:
    """Bootstrap stub — real implementation lands in PR3 (orchestrator)."""
    raise NotImplementedError("jarvis.orchestrator.confirm.confirm: implemented in PR3 (orchestrator)")
