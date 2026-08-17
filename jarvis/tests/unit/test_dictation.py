"""Dictation mode tests.

Tests the voice-to-text injection feature: text accumulation, control
commands (send/exit/clear), and xdotool integration.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock
import pytest

from jarvis.interpreter.dictation import DictationManager, type_text, press_enter


# --- xdotool mocking --------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_xdotool():
    """Mock subprocess calls to xdotool for all tests."""
    with patch("jarvis.interpreter.dictation.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


# --- control command detection -----------------------------------------------
def test_send_command_detected() -> None:
    dm = DictationManager()
    assert dm.is_control_command("enviar") == "send"
    assert dm.is_control_command("listo") == "send"
    assert dm.is_control_command("dale") == "send"
    assert dm.is_control_command("ok") == "send"
    assert dm.is_control_command("enter") == "send"


def test_exit_command_detected() -> None:
    dm = DictationManager()
    assert dm.is_control_command("terminar dictado") == "exit"
    assert dm.is_control_command("salir del dictado") == "exit"
    assert dm.is_control_command("modo comando") == "exit"


def test_clear_command_detected() -> None:
    dm = DictationManager()
    assert dm.is_control_command("borrar") == "clear"
    assert dm.is_control_command("limpiar") == "clear"
    assert dm.is_control_command("borrar todo") == "clear"


def test_regular_text_not_control() -> None:
    dm = DictationManager()
    assert dm.is_control_command("hola mundo") is None
    assert dm.is_control_command("esto es una prueba") is None
    assert dm.is_control_command("¿qué es un observer?") is None


# --- state management --------------------------------------------------------
def test_activate_deactivate() -> None:
    dm = DictationManager()
    assert not dm.is_active
    dm.activate()
    assert dm.is_active
    dm.deactivate()
    assert not dm.is_active


def test_buffer_accumulates_text() -> None:
    dm = DictationManager()
    dm.activate()
    # Regular text adds to buffer (returns False, no response needed)
    should_respond, _ = dm.process_transcript("hola")
    assert not should_respond
    should_respond, _ = dm.process_transcript("mundo")
    assert not should_respond
    # Buffer now has "hola mundo"
    assert dm.state.get_full_text() == "hola mundo"


def test_send_clears_buffer_and_deactivates() -> None:
    dm = DictationManager()
    dm.activate()
    dm.process_transcript("hola")
    should_respond, response = dm.process_transcript("enviar")
    assert should_respond
    assert response == "enviado"
    assert not dm.is_active


def test_exit_deactivates() -> None:
    dm = DictationManager()
    dm.activate()
    dm.process_transcript("texto")
    should_respond, response = dm.process_transcript("terminar dictado")
    assert should_respond
    assert response == "dictado terminado"
    assert not dm.is_active


def test_clear_clears_buffer() -> None:
    dm = DictationManager()
    dm.activate()
    dm.process_transcript("texto a borrar")
    should_respond, response = dm.process_transcript("borrar")
    assert should_respond
    assert response == "borrado"
    assert dm.state.get_full_text() == ""


def test_ignored_when_inactive() -> None:
    dm = DictationManager()
    # Not activated — all text is ignored
    should_respond, _ = dm.process_transcript("hola")
    assert not should_respond
    assert dm.state.get_full_text() == ""


# --- prefix matching ---------------------------------------------------------
def test_send_prefix_detected() -> None:
    dm = DictationManager()
    assert dm.is_control_command("enviar esto") == "send"
    assert dm.is_control_command("listo ya") == "send"


# --- xdotool helpers --------------------------------------------------------
def test_type_text_returns_true(mock_xdotool) -> None:
    assert type_text("hello") is True
    mock_xdotool.assert_called_once()


def test_press_enter_returns_true(mock_xdotool) -> None:
    assert press_enter() is True
    mock_xdotool.assert_called_once()
