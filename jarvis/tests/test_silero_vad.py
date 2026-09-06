"""Tests for SileroVAD in capture.py.

The pip package's ``load_silero_vad(onnx=True)`` is imported *inside*
capture methods (lazy), so the module attribute ``jarvis.audio.capture.silero_vad``
does not exist — patching that name fails. Instead, tests inject a fake
``silero_vad`` module into ``sys.modules`` so the in-function
``from silero_vad import load_silero_vad`` resolves to the mock. A fake
``torch`` is also injected for ``is_speech``'s in-function import.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np

from jarvis.audio.capture import DEFAULT_THRESHOLD, SileroVAD, rms


def _make_silero_vad():
    """Return a fake silero_vad module whose load_silero_vad yields a model."""
    module = ModuleType("silero_vad")
    module.load_silero_vad = MagicMock()
    return module


def _make_torch():
    """Return a fake torch module for is_speech's in-function import."""
    torch = ModuleType("torch")
    torch.no_grad = lambda: MagicMock()  # context manager via MagicMock's __enter__/__exit__
    torch.from_numpy = MagicMock(return_value=MagicMock())
    return torch


def _inject_deps():
    """Patch sys.modules for 'torch' and 'silero_vad' for the test duration."""
    torch = _make_torch()
    silero_vad = _make_silero_vad()
    patcher = patch.dict(sys.modules, {"torch": torch, "silero_vad": silero_vad})
    return patcher, torch, silero_vad


def _prob_tensor(value: float):
    """Return a fake tensor whose .item() yields `value` (ONNX model output)."""
    tensor = MagicMock()
    tensor.item.return_value = value
    return tensor


class TestSileroVAD:
    """Tests for SileroVAD class."""

    def test_init(self):
        vad = SileroVAD(threshold=0.5, sample_rate=16000)
        assert vad.threshold == 0.5
        assert vad.sample_rate == 16000
        assert vad._model is None

    def test_ensure_loaded_success(self):
        """Test successful model loading."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            vad = SileroVAD()
            mock_model = MagicMock()
            silero_vad.load_silero_vad.return_value = mock_model

            result = vad._ensure_loaded()
            assert result is True
            assert vad._model is mock_model
            silero_vad.load_silero_vad.assert_called_once_with(onnx=True)
        finally:
            patcher.stop()

    def test_ensure_loaded_fallback_on_import_error(self):
        """Test fallback when the model fails to load."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            silero_vad.load_silero_vad.side_effect = ImportError("no package")
            vad = SileroVAD()
            result = vad._ensure_loaded()
            assert result is False
            assert vad._init_failed is True
        finally:
            patcher.stop()

    def test_is_speech_empty_block(self):
        """Test empty block returns False (even with model loaded)."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            vad = SileroVAD()
            mock_model = MagicMock()
            mock_model.return_value = _prob_tensor(0.9)
            silero_vad.load_silero_vad.return_value = mock_model
            block = np.array([], dtype=np.float32)
            assert vad.is_speech(block) is False
        finally:
            patcher.stop()

    def test_is_speech_fallback_to_energy(self):
        """Test fallback to energy VAD when Silero not loaded."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            silero_vad.load_silero_vad.side_effect = ImportError("no package")
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
        """Test speech detection with loaded model (probability >= threshold)."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            vad = SileroVAD(threshold=0.5)
            mock_model = MagicMock()
            mock_model.return_value = _prob_tensor(0.9)
            silero_vad.load_silero_vad.return_value = mock_model

            block = np.random.randn(1600).astype(np.float32)
            assert vad.is_speech(block) is True
        finally:
            patcher.stop()

    def test_is_speech_with_model_below_threshold(self):
        """Test silence when probability is below threshold."""
        patcher, _, silero_vad = _inject_deps()
        patcher.start()
        try:
            vad = SileroVAD(threshold=0.5)
            mock_model = MagicMock()
            mock_model.return_value = _prob_tensor(0.2)
            silero_vad.load_silero_vad.return_value = mock_model

            block = np.random.randn(1600).astype(np.float32)
            assert vad.is_speech(block) is False
        finally:
            patcher.stop()

    def test_is_speech_chunks_capture_blocks_for_silero(self):
        """Silero only accepts 512 samples at 16 kHz, not 100 ms blocks."""
        patcher, torch, silero_vad = _inject_deps()
        patcher.start()
        try:
            torch.from_numpy.side_effect = lambda samples: samples
            vad = SileroVAD(threshold=0.5, sample_rate=16000)
            mock_model = MagicMock(return_value=_prob_tensor(0.2))
            silero_vad.load_silero_vad.return_value = mock_model

            assert vad.is_speech(np.zeros(1600, dtype=np.float32)) is False
            assert mock_model.call_count == 3
            assert all(call.args[0].shape == (512,) for call in mock_model.call_args_list)
            assert vad._buffer.size == 64
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
