"""Text-to-speech (bootstrap skeleton).

Design: piper subprocess wrapper (`es_AR-daniela`, 20s timeout) with an async
queue for spoken feedback (RF-4). Real implementation lands in PR5 (voice
pipeline).
"""

from __future__ import annotations


def speak() -> None:
    """Bootstrap stub — real implementation lands in PR5 (voice pipeline)."""
    raise NotImplementedError("jarvis.tts.speak: implemented in PR5 (voice pipeline)")
