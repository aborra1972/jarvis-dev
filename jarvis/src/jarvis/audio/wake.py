"""Wake-word detection (PR5, task 5.2).

Design ADR-3: openWakeWord wrapper gated by a configurable threshold. The
detector implements the orchestrator WakeDetector protocol — wait(timeout) ->
bool (orchestrator.contracts, PR3) — and pulls 16kHz mono float blocks from a
Capturer.

openwakeword 0.4.0 API (verified in PR5): Model(wakeword_model_paths=[...]),
predict(x) -> {model_name: score}. The pretrained hey_jarvis_v0.1.onnx ships
with the package; a custom jarvis.onnx can be dropped in (gate 5.6) and is
preferred when present. After power_off_self the FSM (PR3) keeps the detector
stopped — reactivation is non-vocal only (assistant-lifecycle RF-11).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from jarvis.audio.capture import BLOCK_MS, SAMPLE_RATE, Capturer

DEFAULT_THRESHOLD = 0.5
DEFAULT_VAD_THRESHOLD = 0.5
HEY_JARVIS_MODEL = "hey_jarvis_v0.1.onnx"


class Clock(Protocol):
    def __call__(self) -> float:
        ...


def triggered(scores: dict[str, float], threshold: float) -> bool:
    """True when any model score reaches the threshold (ADR-3 gate)."""
    return any(score >= threshold for score in scores.values())


def _default_model_path() -> Path:
    try:
        import importlib.resources as resources

        with resources.as_file(
            resources.files("openwakeword.resources") / "models" / HEY_JARVIS_MODEL
        ) as path:
            return Path(path)
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        raise RuntimeError(
            f"openwakeword not installed or {HEY_JARVIS_MODEL} missing from its resources"
        ) from exc


def build_model_paths(
    model_paths: list[Path] | None,
    *,
    custom: Path | None = None,
) -> list[Path]:
    """Resolve the ONNX models to load.

    A custom jarvis.onnx (trained gate 5.6) takes precedence; otherwise the
    packaged hey_jarvis_v0.1.onnx is used.
    """
    if model_paths:
        return list(model_paths)
    if custom is not None and custom.is_file():
        return [custom]
    return [_default_model_path()]


class OpenWakeWord:
    """openWakeWord detector implementing the orchestrator WakeDetector."""

    def __init__(
        self,
        capturer: Capturer,
        *,
        model_paths: list[Path] | None = None,
        custom: Path | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        vad_threshold: float = DEFAULT_VAD_THRESHOLD,
        model=None,
        clock: Clock | None = None,
        timeout_per_read: float = 1.0,
    ) -> None:
        self.capturer = capturer
        self.threshold = threshold
        self.vad_threshold = vad_threshold
        self._timeout_per_read = timeout_per_read
        self._clock = clock or _monotonic
        if model is not None:
            self._model = model  # injected fake in tests
        else:
            from openwakeword.model import Model

            paths = [str(p) for p in build_model_paths(model_paths, custom=custom)]
            self._model = Model(
                wakeword_model_paths=paths,
                enable_speex_noise_suppression=False,
                vad_threshold=vad_threshold,
            )

    def wait(self, timeout: float) -> bool:
        """Block until a model score reaches threshold or the timeout elapses."""
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            block = self.capturer.read_frames(timeout=self._timeout_per_read)
            if block is None:
                break
            if triggered(self._model.predict(block), self.threshold):
                return True
        return False


def _monotonic() -> float:
    import time

    return time.monotonic()
