"""Small, hardware-independent audio capture result contracts."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CaptureMode(Enum):
    ORDINARY = "ordinary"
    CONFIRMATION = "confirmation"


class CaptureStatus(Enum):
    UTTERANCE = "utterance"
    SILENCE = "silence"
    NO_FRAME = "no_frame"
    CANCELLED = "cancelled"
    DEVICE_FAILURE = "device_failure"


@dataclass(frozen=True)
class CaptureResult:
    status: CaptureStatus
    blocks: tuple[Any, ...]
    duration_s: float
    onset_seen: bool
    no_frame_polls: int = 0
    error: Exception | None = None
