"""Persistent reminders: parsing, scheduling, notification and restoration."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from jarvis.actions.reminders import ReminderScheduler, parse_reminder_request
from jarvis.interpreter.schema import Intent


class FakeTimer:
    created: list["FakeTimer"] = []

    def __init__(self, delay: float, callback) -> None:
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.started = False
        self.created.append(self)

    def start(self) -> None:
        self.started = True


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> None:
        self.spoken.append(text)


@pytest.fixture(autouse=True)
def _clear_timers() -> None:
    FakeTimer.created.clear()


def test_parse_relative_minutes_with_time_before_message() -> None:
    now = datetime(2026, 9, 6, 10, 0)
    text, due_at = parse_reminder_request(
        "recordame en 10 minutos que saque la ropa",
        now=now,
    )
    assert text == "saque la ropa"
    assert due_at == datetime(2026, 9, 6, 10, 10).timestamp()


def test_parse_relative_half_hour_after_message() -> None:
    now = datetime(2026, 9, 6, 10, 0)
    text, due_at = parse_reminder_request("tomar agua en media hora", now=now)
    assert text == "tomar agua"
    assert due_at == datetime(2026, 9, 6, 10, 30).timestamp()


def test_parse_absolute_pm_and_move_past_time_to_tomorrow() -> None:
    now = datetime(2026, 9, 6, 16, 0)
    text, due_at = parse_reminder_request("llamar a mama a las 3 pm", now=now)
    assert text == "llamar a mama"
    assert due_at == datetime(2026, 9, 7, 15, 0).timestamp()


def test_parse_rejects_missing_time_or_message() -> None:
    with pytest.raises(ValueError, match="cuándo"):
        parse_reminder_request("comprar pan")
    with pytest.raises(ValueError, match="qué querés recordar"):
        parse_reminder_request("en 10 minutos")


def test_scheduler_persists_and_fires_desktop_and_tts_notification(tmp_path) -> None:
    now = datetime(2026, 9, 6, 10, 0)
    commands: list[list[str]] = []
    speaker = FakeSpeaker()
    path = tmp_path / "reminders.json"
    scheduler = ReminderScheduler(
        path,
        speaker=speaker,
        runner=lambda command: commands.append(command) or (0, ""),
        now=lambda: now,
        timer_factory=FakeTimer,
    )

    result = scheduler.handle_set_reminder(
        Intent(intent="set_reminder", entities={"text": "sacar la ropa en 10 minutos"}),
        None,
    )

    assert result.ok is True
    assert len(scheduler.pending()) == 1
    assert json.loads(path.read_text())[0]["text"] == "sacar la ropa"
    assert FakeTimer.created[0].delay == 600
    assert FakeTimer.created[0].daemon is True
    assert FakeTimer.created[0].started is True

    FakeTimer.created[0].callback()

    assert scheduler.pending() == ()
    assert json.loads(path.read_text()) == []
    assert commands == [["notify-send", "Jarvis", "Recordatorio: sacar la ropa"]]
    assert speaker.spoken == ["Recordatorio: sacar la ropa"]


def test_scheduler_restores_persisted_reminders(tmp_path) -> None:
    now = datetime(2026, 9, 6, 10, 0)
    path = tmp_path / "reminders.json"
    path.write_text(json.dumps([
        {
            "id": "saved",
            "text": "revisar el horno",
            "due_at": datetime(2026, 9, 6, 10, 5).timestamp(),
        }
    ]))

    scheduler = ReminderScheduler(path, now=lambda: now, timer_factory=FakeTimer)

    assert [item.id for item in scheduler.pending()] == ["saved"]
    assert FakeTimer.created[0].delay == 300


def test_handler_returns_spoken_error_for_invalid_request(tmp_path) -> None:
    scheduler = ReminderScheduler(tmp_path / "reminders.json", timer_factory=FakeTimer)
    result = scheduler.handle_set_reminder(
        Intent(intent="set_reminder", entities={"text": "comprar pan"}),
        None,
    )
    assert result.ok is False
    assert "No pude crear" in result.spoken
