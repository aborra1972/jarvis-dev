"""Voice pipeline (PR5, design Repo Structure).

Audio layer of the assistant: streaming capture, wake-word detection, speech
recognition, text-to-speech and playback, plus the adapters that wire them to
the orchestrator contracts (orchestrator.contracts, PR3).

Deviation note (PR5): the orchestrator prompt for slice 5 specifies this
package (audio/capture.py, audio/wake.py, ...) instead of the flat modules
listed in design.md Repo Structure — the package layout is the operative
structure for PR5.
"""

from jarvis.audio.capture import (
    BLOCK_MS,
    MAX_UTTERANCE_S,
    SAMPLE_RATE,
    SILENCE_MS,
    Capturer,
    SilenceVAD,
    SoundDeviceCapturer,
    gather_utterance,
    rms,
    write_wav,
)

__all__ = [
    "BLOCK_MS",
    "MAX_UTTERANCE_S",
    "SAMPLE_RATE",
    "SILENCE_MS",
    "Capturer",
    "SilenceVAD",
    "SoundDeviceCapturer",
    "gather_utterance",
    "rms",
    "write_wav",
]
