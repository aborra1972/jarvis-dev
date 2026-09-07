"""Unit contracts for cancellable capture outcomes."""

from jarvis.audio.contracts import CaptureMode, CaptureResult, CaptureStatus


def test_capture_contracts_are_explicit_and_immutable() -> None:
    result = CaptureResult(CaptureStatus.NO_FRAME, (), 0.0, False, 2)
    assert CaptureMode.ORDINARY.value == "ordinary"
    assert CaptureMode.CONFIRMATION.value == "confirmation"
    assert result.status is CaptureStatus.NO_FRAME
    assert result.no_frame_polls == 2
