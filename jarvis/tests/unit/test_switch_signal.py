"""Task 6.3 WU2: RF-11 non-vocal reactivation via signal (señal externa).

The FSM already keeps the loop OFF without consulting the mic/wake (RF-11).
This WU makes the switch cross-process: ``jarvis off``/``jarvis on`` persist
state.json AND signal a running loop (SIGUSR1/SIGUSR2 via a pid file); the
running loop installs handlers that flip the in-memory switch and apply the
MicSwitch mic release/resume. A spoken wake word cannot reactivate it because
no mic is open while OFF.

Signal safety: handlers only set a flag (_switch_pending); the main loop
calls _apply_switch() to execute the real work (session save, mic control).
This prevents corrupted state.json from interrupted writes.
"""

from __future__ import annotations

import json
import os
import signal

from jarvis.orchestrator import loop
from jarvis.orchestrator.session import Session


class _SwitchRecorder:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        return False


def _register_and_send(session: Session, switch, sig: int) -> None:
    loop._register_switch_signals(session, switch)
    try:
        os.kill(os.getpid(), sig)
    finally:
        signal.signal(sig, signal.SIG_DFL)


def test_sigusr1_turns_off_and_applies_switch(tmp_path) -> None:
    session = Session(state_path=str(tmp_path / "state.json"))
    switch = _SwitchRecorder()

    _register_and_send(session, switch, signal.SIGUSR1)
    # Signal handler only sets a flag; _apply_switch processes it safely
    loop._apply_switch(session, switch)

    assert session.switched_off is True
    assert switch.calls == 1
    payload = json.loads((tmp_path / "state.json").read_text())
    assert payload["switched_off"] is True


def test_sigusr2_turns_back_on(tmp_path) -> None:
    session = Session(state_path=str(tmp_path / "state.json"))
    session.switched_off = True
    switch = _SwitchRecorder()

    _register_and_send(session, switch, signal.SIGUSR2)
    loop._apply_switch(session, switch)

    assert session.switched_off is False
    payload = json.loads((tmp_path / "state.json").read_text())
    assert payload["switched_off"] is False


def test_signal_handler_only_sets_flag(tmp_path) -> None:
    """Signal handler must NOT do I/O — only set the pending flag."""
    session = Session(state_path=str(tmp_path / "state.json"))
    switch = _SwitchRecorder()

    loop._register_switch_signals(session, switch)
    try:
        os.kill(os.getpid(), signal.SIGUSR1)
    finally:
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)

    # Flag is set but state NOT changed yet — no I/O in handler
    assert loop._switch_pending is True
    assert session.switched_off is False
    assert not (tmp_path / "state.json").exists()

    # Now process the flag — this is where the real work happens
    loop._apply_switch(session, switch)
    assert session.switched_off is True
    assert switch.calls == 1
    assert (tmp_path / "state.json").exists()


def test_apply_switch_noop_without_pending_flag(tmp_path) -> None:
    """_apply_switch is a no-op when no signal was received."""
    session = Session(state_path=str(tmp_path / "state.json"))
    switch = _SwitchRecorder()

    loop._apply_switch(session, switch)

    assert session.switched_off is False
    assert switch.calls == 0


def test_signal_running_sends_signal_to_pid(tmp_path, monkeypatch) -> None:
    pid_file = tmp_path / "jarvis.pid"
    pid_file.write_text("4242")
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))

    loop._signal_running(signal.SIGUSR1, pid_file=pid_file)

    assert sent == [(4242, signal.SIGUSR1)]


def test_signal_running_noop_without_pid_file(tmp_path, monkeypatch) -> None:
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(os, "kill", lambda pid, sig: sent.append((pid, sig)))

    loop._signal_running(signal.SIGUSR1, pid_file=tmp_path / "missing.pid")

    assert sent == []


def test_signal_running_cleans_stale_pid(tmp_path, monkeypatch) -> None:
    pid_file = tmp_path / "jarvis.pid"
    pid_file.write_text("999999")

    def _dead(pid: int, sig: int) -> None:
        raise ProcessLookupError()

    monkeypatch.setattr(os, "kill", _dead)

    loop._signal_running(signal.SIGUSR1, pid_file=pid_file)

    assert not pid_file.exists()
