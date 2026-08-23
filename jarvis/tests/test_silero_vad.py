"""Tests for SileroVAD in capture.py.

torch is imported *inside* capture methods (lazy), so the module attribute
``jarvis.audio.capture.torch`` does not exist — patching that name fails.
Instead, tests inject a fake torch into ``sys.modules`` so the in-function
``import torch`` resolves to the mock.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np

from jarvis.audio.capture import DEFAULT_THRESHOLD, SileroVAD, rms


def _make_torch():
    """Return a fake torch module whose hub.load yields (model, utils)."""
    torch = ModuleType("torch")
    torch.no_grad = lambda: MagicMock()  # context manager via MagicMock's __enter__/__exit__
    torch.from_numpy = MagicMock(return_value=MagicMock())
    torch.hub = ModuleType("torch.hub")
    torch.hub.load = MagicMock()
    return torch


def _inject_torch():
    """Patch sys.modules['torch'] for the duration of the test."""
    torch = _make_torch()
    patcher = patch.dict(sys.modules, {"torch": torch})
    return patcher, torch


class TestSileroVAD:
    """Tests for SileroVAD class."""

    def test_init(self):
        vad = SileroVAD(threshold=0.5, sample_rate=16000)
        assert vad.threshold == 0.5
        assert vad.sample_rate == 16000
        assert vad._model is None

    def test_ensure_loaded_success(self):
        """Test successful model loading."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            vad = SileroVAD()
            mock_model = MagicMock()
            mock_utils = (MagicMock(), None, None, None, None)
            torch.hub.load.return_value = (mock_model, mock_utils)

            result = vad._ensure_loaded()
            assert result is True
            assert vad._model is mock_model
        finally:
            patcher.stop()

    def test_ensure_loaded_fallback_on_import_error(self):
        """Test fallback when torch.hub.load fails."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            torch.hub.load.side_effect = ImportError("no module")
            vad = SileroVAD()
            result = vad._ensure_loaded()
            assert result is False
            assert vad._init_failed is True
        finally:
            patcher.stop()

    def test_is_speech_empty_block(self):
        """Test empty block returns False (even with model loaded)."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            vad = SileroVAD()
            torch.hub.load.return_value = (MagicMock(), (MagicMock(), None, None, None, None))
            block = np.array([], dtype=np.float32)
            assert vad.is_speech(block) is False
        finally:
            patcher.stop()

    def test_is_speech_fallback_to_energy(self):
        """Test fallback to energy VAD when Silero not loaded."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            torch.hub.load.side_effect = ImportError("no module")
            vad = SileroVAD()
            assert vad._init_failed is False
            # High energy block (speech)
            speech_block = np.full(1600, 0.5, dtype=np.float32)
            assert vad.is_speech(speech_block) is True
            # Low energy block (silence)
            silence_block = np.full(1600, 0.001, dtype=np.float32)
            assert vad.is_speech(silence_block) is False
        finally:
            patcher.stop()

    def test_is_speech_with_model_above_threshold(self):
        """Test speech detection with loaded model (confidence >= threshold)."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            vad = SileroVAD(threshold=0.5)
            mock_model = MagicMock()
            mock_utils = (MagicMock(), None, None, None, None)
            torch.hub.load.return_value = (mock_model, mock_utils)
            # Model returns confidence 0.9 -> speech (Silero: list of timestamp lists)
            mock_model.return_value = [[{"start": 0, "end": 160, "confidence": 0.9}]]

            block = np.random.randn(1600).astype(np.float32)
            assert vad.is_speech(block) is True
        finally:
            patcher.stop()

    def test_is_speech_with_model_below_threshold(self):
        """Test silence when confidence is below threshold."""
        patcher, torch = _inject_torch()
        patcher.start()
        try:
            vad = SileroVAD(threshold=0.5)
            mock_model = MagicMock()
            torch.hub.load.return_value = (mock_model, (MagicMock(), None, None, None, None))
            mock_model.return_value = [[{"start": 0, "end": 160, "confidence": 0.2}]]

            block = np.random.randn(1600).astype(np.float32)
            assert vad.is_speech(block) is False
        finally:
            patcher.stop()

    def test_interface_attributes(self):
        """SileroVAD exposes the duck-typed capture interface (T-VAD-02)."""
        vad = SileroVAD(silence_s=0.8, max_s=10.0)
        assert vad.block_duration == 0.1
        assert vad.silence_s == 0.8
        assert vad.max_s == 10.0
        assert vad.sample_rate == 16000

    def test_rms_function(self):
        """Test RMS calculation."""
        # Silence should have low RMS
        silence = np.zeros(1600, dtype=np.float32)
        assert rms(silence) < DEFAULT_THRESHOLD

        # Loud signal should have high RMS
        loud = np.full(1600, 0.5, dtype=np.float32)
        assert rms(loud) >= DEFAULT_THRESHOLD

    def test_rms_empty(self):
        """Test RMS of empty array."""
        assert rms(np.array([], dtype=np.float32)) == 0.0
