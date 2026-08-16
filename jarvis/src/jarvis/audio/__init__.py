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
from jarvis.audio.wake import (
    DEFAULT_THRESHOLD as WAKE_DEFAULT_THRESHOLD,
    OpenWakeWord,
    triggered,
)
from jarvis.audio.stt import (
    GATE_DURATION_S as STT_GATE_DURATION_S,
    STT_TIMEOUT_S,
    STTError,
    WhisperSTT,
    select_model,
)

from jarvis.audio.tts import EDGE_TTS_TIMEOUT_S, TTS_TIMEOUT_S, TTSError, EdgeTTS, PiperTTS
from jarvis.audio.playback import DEFAULT_MP3_PLAYER, DEFAULT_PLAYER, Playback, PlaybackError
from jarvis.audio.pipeline import MicSwitch, PiperSpeaker, UtteranceCapture

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
    "WAKE_DEFAULT_THRESHOLD",
    "OpenWakeWord",
    "triggered",
    "STT_GATE_DURATION_S",
    "STT_TIMEOUT_S",
    "STTError",
    "WhisperSTT",
    "select_model",
    "TTS_TIMEOUT_S",
    "EDGE_TTS_TIMEOUT_S",
    "TTSError",
    "PiperTTS",
    "EdgeTTS",
    "DEFAULT_PLAYER",
    "DEFAULT_MP3_PLAYER",
    "Playback",
    "PlaybackError",
    "MicSwitch",
    "PiperSpeaker",
    "UtteranceCapture",
]
