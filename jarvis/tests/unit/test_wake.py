from __future__ import annotations

from collections import deque

import numpy as np
import pytest

from jarvis.audio.capture import BLOCK_MS, SAMPLE_RATE, SilenceVAD, rms
from jarvis.audio.wake import SpeechStartWake
import jarvis.audio.wake as wake_module


BLOCK = SAMPLE_RATE * BLOCK_MS // 1000


class FakeCapturer:
    def __init__(self, blocks: list[np.ndarray]) -> None:
        self.blocks = deque(blocks)

    def read_frames(self, timeout: float = 1.0) -> np.ndarray | None:
        return self.blocks.popleft() if self.blocks else None


def _tone(amplitude: float) -> np.ndarray:
    return (amplitude * np.sin(2 * np.pi * 220 * np.arange(BLOCK) / SAMPLE_RATE)).astype(
        np.float32
    )


def test_energy_fallback_maps_gui_threshold_below_realistic_speech(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wake_module,
        "build_vad",
        lambda **kwargs: SilenceVAD(threshold=kwargs["threshold"]),
    )
    wake = SpeechStartWake(FakeCapturer([_tone(0.155)]), threshold=0.71)

    assert wake._vad.threshold < rms(_tone(0.155))
    assert wake.wait(timeout=1.0) is True


def test_energy_fallback_does_not_trigger_on_ambient_noise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        wake_module,
        "build_vad",
        lambda **kwargs: SilenceVAD(threshold=kwargs["threshold"]),
    )
    wake = SpeechStartWake(FakeCapturer([_tone(0.02)]), threshold=0.71)

    assert wake.wait(timeout=1.0) is False
