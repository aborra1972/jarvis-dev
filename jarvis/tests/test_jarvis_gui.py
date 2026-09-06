"""Behavior tests for the system-Python GTK control panel."""

from __future__ import annotations

import importlib.util
import signal
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture()
def gui_module(monkeypatch):
    gi = ModuleType("gi")
    gi.require_version = lambda *_: None
    repository = ModuleType("gi.repository")
    for name in ("Gdk", "GLib", "Gtk", "Pango"):
        setattr(repository, name, SimpleNamespace())
    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)

    path = Path(__file__).parents[2] / "jarvis_gui.py"
    spec = importlib.util.spec_from_file_location("jarvis_gui_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_is_running_rejects_stale_pid_reused_by_other_process(gui_module, tmp_path, monkeypatch):
    pid_file = tmp_path / "jarvis.pid"
    pid_file.write_text("4242")
    monkeypatch.setattr(gui_module, "PID_FILE", pid_file)
    monkeypatch.setattr(gui_module.os, "kill", lambda *_: None)
    monkeypatch.setattr(gui_module, "_process_is_jarvis", lambda pid: False)

    assert gui_module._is_running() is False
    assert not pid_file.exists()


def test_power_off_signals_running_process_instead_of_killing_it(gui_module, monkeypatch):
    sent = []
    monkeypatch.setattr(gui_module, "_is_running", lambda: True)
    monkeypatch.setattr(gui_module, "_send_signal", lambda sig: sent.append(sig) or True)
    monkeypatch.setattr(gui_module, "_update_state", lambda **changes: None)
    app = object.__new__(gui_module.JarvisGUI)
    app._is_on = True
    app._user_off = False
    app._log = lambda *_: None
    app._update_ui = lambda: None
    app._launch_jarvis = lambda: pytest.fail("must not restart Jarvis")

    app._on_power_clicked(None)

    assert sent == [signal.SIGUSR1]
    assert app._is_on is False


def test_power_on_signals_existing_off_process(gui_module, monkeypatch):
    sent = []
    monkeypatch.setattr(gui_module, "_is_running", lambda: True)
    monkeypatch.setattr(gui_module, "_send_signal", lambda sig: sent.append(sig) or True)
    monkeypatch.setattr(gui_module, "_update_state", lambda **changes: None)
    app = object.__new__(gui_module.JarvisGUI)
    app._is_on = False
    app._user_off = True
    app._log = lambda *_: None
    app._update_ui = lambda: None
    app._launch_jarvis = lambda: pytest.fail("must not start a duplicate")

    app._on_power_clicked(None)

    assert sent == [signal.SIGUSR2]
    assert app._is_on is True


def test_launch_attaches_to_existing_process_without_restart(gui_module, monkeypatch):
    monkeypatch.setattr(gui_module, "_is_running", lambda: True)
    monkeypatch.setattr(gui_module, "_state_switch_is_off", lambda: False)
    monkeypatch.setattr(
        gui_module.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("must not start a duplicate"),
    )
    app = object.__new__(gui_module.JarvisGUI)
    app._is_on = False
    app._user_off = False
    app._jarvis_proc = None
    app._log = lambda *_: None
    app._update_ui = lambda: None

    assert app._launch_jarvis() is False
    assert app._is_on is True


def test_runtime_text_uses_active_assistant_name(gui_module, tmp_path, monkeypatch):
    state_file = tmp_path / "state.json"
    state_file.write_text('{"agent": "friday"}')
    monkeypatch.setattr(gui_module, "STATE_FILE", state_file)

    assert gui_module._personalize_runtime_text("[jarvis] Jarvis listo") == "[Friday] Friday listo"


def test_read_output_flips_iniciando_to_esperando_activacion(gui_module, monkeypatch):
    """A boot ``listo`` line on the runtime stdout moves the status detail off
    the stuck ``Iniciando...`` state (regression: gemini/Silero boots print
    nothing else, which left the GUI awaiting a line that never arrived)."""
    calls: list[str] = []

    class _Recorder:
        def set_text(self, text: str) -> None:
            calls.append(text)

    class _Proc:
        stdout = ["[jarvis] listo — esperando activación"]

        def wait(self) -> int:
            return 0

    app = object.__new__(gui_module.JarvisGUI)
    app._jarvis_proc = _Proc()
    app._log = lambda *_: None
    app._status_detail = _Recorder()
    exits: list[tuple[object, int]] = []
    app._on_jarvis_exit = lambda process, code: exits.append((process, code))

    monkeypatch.setattr(gui_module, "_read_agent_preference", lambda: "jarvis")
    monkeypatch.setattr(
        gui_module.GLib, "idle_add", lambda fn, *args, **kwargs: fn(*args, **kwargs),
        raising=False,
    )
    gui_module.JarvisGUI._read_output(app)

    assert "Esperando activación..." in calls
    assert exits and exits[0][0] is app._jarvis_proc and exits[0][1] == 0
