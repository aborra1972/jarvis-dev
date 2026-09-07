"""Persistent background reminders with desktop and spoken notifications."""

from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from jarvis import config
from jarvis.actions import base
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult

_RELATIVE_TIME = re.compile(
    r"\ben\s+(?P<amount>\d+(?:[.,]\d+)?|un|una|media)\s+"
    r"(?P<unit>minutos?|horas?)\b"
)
_ABSOLUTE_TIME = re.compile(
    r"\ba\s+las?\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?"
    r"(?:\s*(?P<ampm>am|pm))?\b"
)
_LEADING_COMMAND = re.compile(r"^(?:recordame|recordar|recuerdame)\s+")


@dataclass(frozen=True)
class Reminder:
    id: str
    text: str
    due_at: float


def parse_reminder_request(request: str, *, now: datetime | None = None) -> tuple[str, float]:
    """Parse a reminder message and its relative or wall-clock due time."""
    current = now or datetime.now()
    normalized = " ".join(request.lower().strip().split())
    normalized = _LEADING_COMMAND.sub("", normalized)

    match = _RELATIVE_TIME.search(normalized)
    if match is not None:
        raw_amount = match.group("amount")
        if raw_amount in {"un", "una"}:
            amount = 1.0
        elif raw_amount == "media":
            amount = 0.5
        else:
            amount = float(raw_amount.replace(",", "."))
        unit = match.group("unit")
        seconds = amount * (3600 if unit.startswith("hora") else 60)
        if seconds <= 0:
            raise ValueError("el tiempo debe ser mayor que cero")
        due = current + timedelta(seconds=seconds)
    else:
        match = _ABSOLUTE_TIME.search(normalized)
        if match is None:
            raise ValueError("indicá cuándo, por ejemplo 'en 10 minutos' o 'a las 15:30'")
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        ampm = match.group("ampm")
        if minute > 59 or hour > (12 if ampm else 23) or hour == 0 and ampm:
            raise ValueError("la hora indicada no es válida")
        if ampm:
            hour = hour % 12 + (12 if ampm == "pm" else 0)
        due = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= current:
            due += timedelta(days=1)

    text = (normalized[: match.start()] + " " + normalized[match.end() :]).strip(" ,.-")
    text = re.sub(r"^(?:que|para que|de)\s+", "", text).strip()
    if not text:
        raise ValueError("indicá qué querés recordar")
    return text, due.timestamp()


class ReminderScheduler:
    """Persist reminders and arm daemon timers for pending entries."""

    def __init__(
        self,
        path: Path,
        *,
        speaker: object | None = None,
        runner: Callable[[list[str]], tuple[int, str]] = base.safe_run,
        now: Callable[[], datetime] = datetime.now,
        timer_factory: Callable[[float, Callable[[], None]], object] = threading.Timer,
    ) -> None:
        self.path = Path(path)
        self.speaker = speaker
        self._runner = runner
        self._now = now
        self._timer_factory = timer_factory
        self._lock = threading.RLock()
        self._reminders: dict[str, Reminder] = {}
        self._timers: dict[str, object] = {}
        self._load()

    def schedule(self, request: str) -> Reminder:
        text, due_at = parse_reminder_request(request, now=self._now())
        reminder = Reminder(id=uuid.uuid4().hex, text=text, due_at=due_at)
        with self._lock:
            self._reminders[reminder.id] = reminder
            self._persist()
            self._arm(reminder)
        return reminder

    def handle_set_reminder(self, intent: Intent, session: object) -> ActionResult:
        try:
            reminder = self.schedule(intent.entities.get("text", ""))
        except (OSError, ValueError) as exc:
            return ActionResult(
                ok=False,
                spoken=f"No pude crear el recordatorio, {config.agent_address()}: {exc}.",
            )
        due = datetime.fromtimestamp(reminder.due_at).strftime("%H:%M")
        return ActionResult(
            ok=True,
            spoken=f"Recordatorio programado para las {due}, {config.agent_address()}.",
            data={"reminder_id": reminder.id, "due_at": reminder.due_at},
        )

    def pending(self) -> tuple[Reminder, ...]:
        with self._lock:
            return tuple(sorted(self._reminders.values(), key=lambda item: item.due_at))

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            payload = []
        if not isinstance(payload, list):
            return
        for item in payload:
            try:
                reminder = Reminder(
                    id=str(item["id"]),
                    text=str(item["text"]),
                    due_at=float(item["due_at"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._reminders[reminder.id] = reminder
            self._arm(reminder)

    def _persist(self) -> None:
        payload = [asdict(item) for item in self.pending()]
        base.atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _arm(self, reminder: Reminder) -> None:
        delay = max(0.0, reminder.due_at - self._now().timestamp())
        timer = self._timer_factory(delay, lambda: self._fire(reminder.id))
        if hasattr(timer, "daemon"):
            timer.daemon = True
        self._timers[reminder.id] = timer
        timer.start()

    def _fire(self, reminder_id: str) -> None:
        with self._lock:
            reminder = self._reminders.pop(reminder_id, None)
            self._timers.pop(reminder_id, None)
            if reminder is None:
                return
            self._persist()
        message = f"Recordatorio: {reminder.text}"
        self._runner(["notify-send", config.agent_name(), message])
        speak = getattr(self.speaker, "speak", None)
        if callable(speak):
            speak(message)


def unavailable(intent: Intent, session: object) -> ActionResult:
    return ActionResult(ok=False, spoken="Los recordatorios no están disponibles en este modo.")
