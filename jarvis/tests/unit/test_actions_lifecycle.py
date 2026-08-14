"""Assistant lifecycle executors (PR4, task 4.7): power_off_self, help.

Design (binding: single location): power_off_self lives ONLY here and is
golden-gated + 15s-confirmed by the orchestrator; the executor only logs and
acknowledges. handle_help enumerates the 15-command allowlist.
"""

from __future__ import annotations

from jarvis.actions import assistant_lifecycle, base
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


def test_power_off_self_logs_and_acknowledges(monkeypatch) -> None:
    logged = []
    monkeypatch.setattr(assistant_lifecycle.base, "log", lambda event: logged.append(event))
    result = assistant_lifecycle.power_off_self(_intent("power_off_self"), None)
    assert result.ok is True
    assert logged == ["power_off_self"]


def test_handle_help_lists_all_commands(monkeypatch) -> None:
    result = assistant_lifecycle.handle_help(_intent("help"), None)
    assert result.ok is True
    for command in ALLOWED_INTENTS - {"unknown"}:
        assert command in result.spoken
