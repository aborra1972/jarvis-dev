"""Speech-to-text (bootstrap skeleton).

Design: whisper-cli small subprocess wrapper (`-l es -b 1 --vad --prompt`,
15s timeout, non-zero exit ⇒ spoken error) for local rioplatense Spanish (RNF-2,
M3). Real implementation lands in PR5 (voice pipeline).
"""

from __future__ import annotations


def transcribe() -> None:
    """Bootstrap stub — real implementation lands in PR5 (voice pipeline)."""
    raise NotImplementedError("jarvis.stt.transcribe: implemented in PR5 (voice pipeline)")
