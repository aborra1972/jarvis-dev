"""Wake-word detection (PR5, task 5.2) + custom XLSR classifier (gate 5.6).

Design ADR-3: openWakeWord wrapper gated by a configurable threshold. The
detector implements the orchestrator WakeDetector protocol — wait(timeout) ->
bool (orchestrator.contracts, PR3) — and pulls 16kHz mono float blocks from a
Capturer.

Three backends:
- SpeechStartWake (default, engine "name"): bare-agent-name activation. The
  VAD's speech LEADING EDGE fires (no ML model) and rewind() re-injects the
  ~2s pre-roll that contains the agent name the user is speaking right now;
  the loop's name gate verifies the transcript starts with the agent name.
- OpenWakeWord (engine "openwakeword"): pretrained hey_jarvis_v0.1.onnx from
  the package.
- XLSRWakeWord (gate 5.6): custom wav2vec2-XLSR + LogisticRegression trained
  on the operator's own voice for "jarvis" (single word, Argentine Spanish).

Config.WAKE_ENGINE selects the backend: "name" (default), "openwakeword" or
"xslr".
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Protocol
import warnings

import numpy as np

from jarvis import config
from jarvis.audio.capture import (
    BLOCK_MS,
    SAMPLE_RATE,
    Capturer,
    SilenceVAD,
    build_vad,
)

DEFAULT_THRESHOLD = 0.7
DEFAULT_VAD_THRESHOLD = 0.6
HEY_JARVIS_MODEL = "hey_jarvis_v0.1.onnx"

# XLSR wake word constants
XLSR_WINDOW_S = 2.0       # audio window for XLSR inference
XLSR_HOP_S = 1.0          # hop between windows (1s overlap)
XLSR_MODEL_NAME = "facebook/wav2vec2-large-xlsr-53"


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
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message="Specified provider 'CUDAExecutionProvider'.*",
                    category=UserWarning,
                )
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
            # openwakeword expects flat int16 PCM ([-32768, 32767]). The
            # capturer delivers normalized float32 ([-1, 1]) shaped (frames, 1)
            # from sounddevice: the 2D shape makes the melspectrogram Conv fail
            # ("Invalid input shape"), and feeding the raw floats truncates the
            # signal to silence inside openwakeword's int16 cast. Flatten and
            # rescale before predict (ADR-3 wake path).
            if isinstance(block, np.ndarray):
                if block.ndim > 1:
                    block = block.reshape(-1)
                if np.issubdtype(block.dtype, np.floating):
                    block = (block * 32767).astype(np.int16)
            if triggered(self._model.predict(block), self.threshold):
                return True
        return False

    def flush(self) -> None:
        """Reset openwakeword internal state (call after TTS cooldown)."""
        self._model.reset()


class SpeechStartWake:
    """Name-gated activation (engine "name").

    Instead of a keyword-spotting model, wait() watches the mic with the
    same VAD the capture stage uses and fires on the LEADING EDGE of speech
    (silence -> speech). The agent name and the command are one utterance
    ("friday, abri firefox"), so the last ~preroll_s of audio are kept in a
    ring buffer; rewind() pushes them back into the capturer so the STT sees
    the name too and the orchestrator's name gate can verify it.

    Implements the WakeDetector protocol: wait(timeout)->bool, flush().
    gates_by_name=True tells the loop to apply the transcript name gate
    (and to skip mic-stop/beep between wake and capture, which would clip
    the utterance). The GUI wake threshold maps to `threshold` (Silero
    speech probability; clamped to RMS scale for the energy-VAD fallback).
    """

    gates_by_name = True

    def __init__(
        self,
        capturer: Capturer,
        *,
        threshold: float = DEFAULT_VAD_THRESHOLD,
        preroll_s: float = config.WAKE_PREROLL_S,
        timeout_per_read: float = 1.0,
        vad=None,
        clock: Clock | None = None,
    ) -> None:
        self.capturer = capturer
        self.threshold = threshold
        self._timeout_per_read = timeout_per_read
        self._clock = clock or _monotonic
        self._preroll_target = int(preroll_s * SAMPLE_RATE)
        self._preroll: deque[np.ndarray] = deque()
        self._preroll_samples = 0
        self._was_speech = False
        if vad is not None:
            self._vad = vad
        else:
            self._vad = build_vad(
                engine=config.VAD_ENGINE if config.VAD_ENGINE == "energy" else "silero",
                threshold=threshold,
                sample_rate=SAMPLE_RATE,
                block_ms=BLOCK_MS,
            )
            # Energy fallback: the GUI slider is a Silero probability, not an
            # RMS gate — clamp so a raised slider can't deafen the mic.
            if isinstance(self._vad, SilenceVAD):
                self._vad.threshold = min(0.15, max(0.02, threshold))

    def wait(self, timeout: float) -> bool:
        """Block until speech onset (leading edge) or the timeout elapses."""
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            block = self.capturer.read_frames(timeout=self._timeout_per_read)
            if block is None:
                break
            if isinstance(block, np.ndarray) and block.ndim > 1:
                block = block.reshape(-1)
            self._push_preroll(block)
            speech = self._vad.is_speech(block)
            if speech and not self._was_speech:
                self._was_speech = True
                return True
            self._was_speech = speech
        return False

    def rewind(self) -> bool:
        """Push the pre-roll back into the capturer so the name is not lost.

        Returns True when any block was re-injected (silent wake fires leave
        the mic untouched and need no rewind).
        """
        blocks = list(self._preroll)
        enqueue = getattr(self.capturer, "enqueue_back", None)
        if callable(enqueue) and blocks:
            enqueue(blocks)
        self.flush()
        return bool(blocks)

    def flush(self) -> None:
        """Discard the pre-roll and VAD state (call after TTS cooldown)."""
        self._preroll.clear()
        self._preroll_samples = 0
        self._was_speech = False
        reset = getattr(self._vad, "reset", None)
        if callable(reset):
            reset()

    def _push_preroll(self, block: np.ndarray) -> None:
        self._preroll.append(block)
        self._preroll_samples += len(block)
        while self._preroll_samples > self._preroll_target and self._preroll:
            dropped = self._preroll.popleft()
            self._preroll_samples -= len(dropped)


class XLSRWakeWord:
    """Custom wake word detector using wav2vec2-XLSR + trained classifier.

    Accumulates audio into 2-second windows, extracts XLSR embeddings
    (max-pool), and classifies with the trained ONNX LogisticRegression model.
    Implements the same WakeDetector protocol as OpenWakeWord.
    """

    def __init__(
        self,
        capturer: Capturer,
        *,
        classifier_path: Path,
        threshold: float = DEFAULT_THRESHOLD,
        window_s: float = XLSR_WINDOW_S,
        hop_s: float = XLSR_HOP_S,
        model_name: str = XLSR_MODEL_NAME,
        model=None,
        clock: Clock | None = None,
        timeout_per_read: float = 0.5,
    ) -> None:
        self.capturer = capturer
        self.threshold = threshold
        self._window_samples = int(window_s * SAMPLE_RATE)
        self._hop_samples = int(hop_s * SAMPLE_RATE)
        self._timeout_per_read = timeout_per_read
        self._clock = clock or _monotonic
        self._buf: deque[np.ndarray] = deque()
        self._buf_samples = 0

        if model is not None:
            self._xlsr = None
            self._feature_extractor = None
            self._classifier = None
            self._onnx_session = model  # injected fake in tests
        else:
            import onnxruntime as ort
            from transformers import Wav2Vec2Model, Wav2Vec2FeatureExtractor

            self._feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                model_name, local_files_only=True
            )
            self._xlsr = Wav2Vec2Model.from_pretrained(
                model_name, local_files_only=True
            )
            self._xlsr.eval()

            self._onnx_session = ort.InferenceSession(str(classifier_path))

    def wait(self, timeout: float) -> bool:
        """Block until the classifier score reaches threshold or timeout."""
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            block = self.capturer.read_frames(timeout=self._timeout_per_read)
            if block is None:
                break

            # Flatten to mono float32
            if isinstance(block, np.ndarray):
                if block.ndim > 1:
                    block = block.reshape(-1)
                if np.issubdtype(block.dtype, np.floating):
                    pass  # already float32 [-1, 1]
                else:
                    block = block.astype(np.float32) / 32767.0

            self._buf.append(block)
            self._buf_samples += len(block)

            # Process when we have a full window
            if self._buf_samples >= self._window_samples:
                window = np.concatenate(list(self._buf))
                window = window[: self._window_samples]  # trim to exact size

                score = self._classify(window)
                if score >= self.threshold:
                    return True

                # Slide window by hop
                drop_samples = self._hop_samples
                while drop_samples > 0 and self._buf:
                    front = self._buf[0]
                    if len(front) <= drop_samples:
                        drop_samples -= len(front)
                        self._buf.popleft()
                        self._buf_samples -= len(front)
                    else:
                        self._buf[0] = front[drop_samples:]
                        self._buf_samples -= drop_samples
                        drop_samples = 0

        return False

    def flush(self) -> None:
        """Discard accumulated audio buffer (call after TTS cooldown)."""
        self._buf.clear()
        self._buf_samples = 0

    def _classify(self, audio: np.ndarray) -> float:
        """Run XLSR + ONNX classifier on a2s audio window. Returns score."""
        import torch

        # Extract XLSR embeddings
        inputs = self._feature_extractor(
            [audio],
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
            padding=True,
        )
        with torch.no_grad():
            outputs = self._xlsr(**inputs)

        hidden = outputs.last_hidden_state.squeeze(0).numpy()  # (seq_len, 1024)
        # Max-pool over time axis
        embedding = hidden.max(axis=0, keepdims=True).astype(np.float32)  # (1, 1024)

        # ONNX classifier
        input_name = self._onnx_session.get_inputs()[0].name
        result = self._onnx_session.run(None, {input_name: embedding})
        proba = _positive_class_probability(result)
        print(f"[jarvis] wake score: {proba:.3f} (threshold={self.threshold})", flush=True)
        return proba


def build_wake_detector(
    capturer: Capturer,
    *,
    engine: str = "openwakeword",
    classifier_path: Path | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    **kwargs,
) -> OpenWakeWord | XLSRWakeWord | SpeechStartWake:
    """Factory: select wake word backend based on config.

    engine="name" uses SpeechStartWake (VAD speech-leading-edge activation
    with pre-roll rewind for the bare agent name; no ML model).
    engine="xslr" uses the custom trained classifier (gate 5.6).
    engine="openwakeword" (default) uses the pretrained hey_jarvis model.
    """
    if engine == "name":
        return SpeechStartWake(capturer, threshold=threshold, **kwargs)
    if engine == "xslr":
        if classifier_path is None or not classifier_path.is_file():
            raise FileNotFoundError(
                f"XLSR classifier not found: {classifier_path}\n"
                "Train it first: python train/entrenar_clasificador.py --export-onnx"
            )
        return XLSRWakeWord(
            capturer,
            classifier_path=classifier_path,
            threshold=threshold,
            **kwargs,
        )
    return OpenWakeWord(capturer, threshold=threshold, **kwargs)


def _positive_class_probability(outputs: list) -> float:
    """Extract class-1 probability from sklearn-onnx classifier outputs."""
    if len(outputs) < 2:
        raise ValueError("wake classifier did not return probabilities")
    probabilities = outputs[1]
    first = probabilities[0] if isinstance(probabilities, (list, tuple)) else probabilities
    if isinstance(first, dict):
        value = first.get(1, first.get("1"))
        if value is None:
            raise ValueError("wake classifier has no positive class probability")
        return float(value)
    values = np.asarray(first, dtype=np.float32).reshape(-1)
    if values.size < 2:
        raise ValueError("wake classifier probability tensor has no positive class")
    return float(values[1])


def _monotonic() -> float:
    import time

    return time.monotonic()
