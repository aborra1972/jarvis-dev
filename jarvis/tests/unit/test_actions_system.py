"""System executors (PR4, task 4.4): shutdown/reboot via systemctl, open_app allowlisted.

Design (RF-8, threat matrix): destructive actions run behind the orchestrator's
15s confirm gate and are logged; open_app only ever spawns xdg-open with an
allowlisted app (disallowed app ⇒ rejected, nothing spawned). Every subprocess
is list-args via base.safe_run (no shell).
"""

from __future__ import annotations

import pytest

from jarvis.actions import system
from jarvis.config import ALLOWED_APPS
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


def _monkeypatch_safe_run(monkeypatch):
    commands = []
    monkeypatch.setattr(
        system.base,
        "safe_run",
        lambda command, timeout=20.0: commands.append(command) or (0, ""),
    )
    return commands


def test_shutdown_runs_systemctl_poweroff(monkeypatch) -> None:
    commands = _monkeypatch_safe_run(monkeypatch)
    logged = []
    monkeypatch.setattr(system.base, "log", lambda event: logged.append(event))
    result = system.shutdown(_intent("shutdown"), None)
    assert result.ok is True
    assert commands == [["systemctl", "poweroff"]]
    assert logged == ["shutdown"]


def test_reboot_runs_systemctl_reboot(monkeypatch) -> None:
    commands = _monkeypatch_safe_run(monkeypatch)
    result = system.reboot(_intent("reboot"), None)
    assert result.ok is True
    assert commands == [["systemctl", "reboot"]]


def test_open_app_allowlisted_spawns_command(monkeypatch) -> None:
    commands = _monkeypatch_safe_run(monkeypatch)
    result = system.open_app(_intent("open_app", {"app": "firefox"}), None)
    assert result.ok is True
    assert commands == [["firefox"]]


def test_open_app_disallowed_is_rejected_and_never_spawns(monkeypatch) -> None:
    commands = _monkeypatch_safe_run(monkeypatch)
    result = system.open_app(_intent("open_app", {"app": "rm"}), None)
    assert result.ok is False
    assert "permitida" in result.spoken
    assert commands == []


def test_open_app_unknown_app_is_rejected(monkeypatch) -> None:
    commands = _monkeypatch_safe_run(monkeypatch)
    result = system.open_app(_intent("open_app", {"app": "netcat"}), None)
    assert result.ok is False
    assert commands == []


def test_system_failure_degrades_to_spoken_error(monkeypatch) -> None:
    monkeypatch.setattr(
        system.base,
        "safe_run",
        lambda command, timeout=20.0: (1, "denied"),
    )
    result = system.reboot(_intent("reboot"), None)
    assert result.ok is False
    assert "no pude" in result.spoken
