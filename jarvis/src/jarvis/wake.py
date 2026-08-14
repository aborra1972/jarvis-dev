"""Wake word detection (bootstrap skeleton).

Design: openWakeWord wrapper (onnx) with threshold, gating all audio processing
on the configured wake word (RF-1). Real implementation lands in PR5 (voice
pipeline, incl. custom rioplatense model training gate).
"""

from __future__ import annotations


def detect() -> None:
    """Bootstrap stub — real implementation lands in PR5 (voice pipeline)."""
    raise NotImplementedError("jarvis.wake.detect: implemented in PR5 (voice pipeline)")
