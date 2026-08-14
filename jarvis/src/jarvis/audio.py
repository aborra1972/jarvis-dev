"""Audio capture (bootstrap skeleton).

Design: sounddevice streaming capture loop + energy VAD producing 16kHz mono
float frames for the wake-word detector. Real implementation lands in PR5
(voice pipeline).
"""

from __future__ import annotations


def capture() -> None:
    """Bootstrap stub — real implementation lands in PR5 (voice pipeline)."""
    raise NotImplementedError("jarvis.audio.capture: implemented in PR5 (voice pipeline)")
