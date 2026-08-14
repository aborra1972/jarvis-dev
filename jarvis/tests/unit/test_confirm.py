"""Verbal confirmation gate tests (PR3, task 3.2).

M6: shutdown/reboot/power_off_self always require verbal confirmation. The
15s window runs on an injectable Clock so all three paths — yes, no, timeout —
are exercised without waiting (design sequence diagram b).
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.confirm import (
    CONFIRM_CANCEL_SPOKEN,
    CONFIRM_TIMEOUT_S,
    Confirmation,
    classify_response,
    confirm,
)


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class FakeCapture:
    def __init__(self, responses: list[str | None]) -> None:
        self.responses = list(responses)

    def capture(self) -> str | None:
        return self.responses.pop(0) if self.responses else None


class FakeSpeaker:
    def __init__(self) -> None:
        self.said: list[str] = []

    def speak(self, text: str) -> None:
        self.said.append(text)


DESTRUCTIVE = Intent(intent="shutdown", entities={}, confidence=1.0, confirm_required=True)


def _run(responses: list[str | None], advance: float = 0.0) -> tuple[Confirmation, FakeSpeaker]:
    clock = FakeClock()
    capture = FakeCapture(responses)
    speaker = FakeSpeaker()

    def advancing_capture():
        clock.advance(advance)
        return capture.capture()

    verdict = confirm(DESTRUCTIVE, clock=clock, capture=advancing_capture, speaker=speaker)
    return verdict, speaker


def test_confirm_proceeds_on_yes() -> None:
    verdict, speaker = _run(["sí"])
    assert verdict is Confirmation.CONFIRMED
    assert "confirm" in speaker.said[0].lower()
    assert len(speaker.said) == 1


def test_confirm_aborts_on_no() -> None:
    verdict, speaker = _run(["no"])
    assert verdict is Confirmation.ABORTED
    assert speaker.said[-1] == CONFIRM_CANCEL_SPOKEN


def test_confirm_times_out_after_15s_of_silence() -> None:
    clock = FakeClock()
    speaker = FakeSpeaker()

    def silence_until_deadline():
        clock.advance(CONFIRM_TIMEOUT_S + 0.1)
        return None

    verdict = confirm(DESTRUCTIVE, clock=clock, capture=silence_until_deadline, speaker=speaker)
    assert verdict is Confirmation.TIMED_OUT
    assert "cancel" in speaker.said[-1]


def test_unclear_answer_keeps_listening_then_confirms() -> None:
    clock = FakeClock()
    capture = FakeCapture(["¿qué?", "dale"])
    speaker = FakeSpeaker()
    verdict = confirm(DESTRUCTIVE, clock=clock, capture=capture.capture, speaker=speaker)
    assert verdict is Confirmation.CONFIRMED


@pytest.mark.parametrize(
    "text,expected",
    [
        ("sí", Confirmation.CONFIRMED),
        ("si, dale", Confirmation.CONFIRMED),
        ("dale nomás", Confirmation.CONFIRMED),
        ("confirmo", Confirmation.CONFIRMED),
        ("jarvis, sí", Confirmation.CONFIRMED),
        ("no", Confirmation.ABORTED),
        ("no, no lo hagas", Confirmation.ABORTED),
        ("negativo", Confirmation.ABORTED),
        ("para", Confirmation.ABORTED),
        ("no sé", Confirmation.ABORTED),
        ("repetí", None),
        ("", None),
    ],
)
def test_classify_response(text: str, expected: Confirmation | None) -> None:
    assert classify_response(text) is expected


def test_confirm_timeout_constant() -> None:
    assert CONFIRM_TIMEOUT_S == 15.0
