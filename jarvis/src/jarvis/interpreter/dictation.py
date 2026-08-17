"""Dictation mode — voice-to-text injection for focused applications.

When a code editor (OpenCode, VS Code, etc.) has focus, Jarvis enters
dictation mode: transcribed speech is typed directly into the focused
input field using xdotool. The user controls the mode with voice commands:

- "enviar" / "listo" → sends the accumulated text (Enter key)
- "terminar dictado" / "salir del dictado" → exits dictation mode
- "borrar" / "limpiar" → clears the current buffer without sending

The dictation mode is toggled by the orchestrator based on window focus.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.interpreter")

# Dictation control patterns (Spanish rioplatense)
_SEND_COMMANDS: frozenset[str] = frozenset({
    "enviar", "envialo", "mandalo", "mandar", "listo", "dale", "ok",
    "enter", "confirmar", "confirmalo",
})
_EXIT_COMMANDS: frozenset[str] = frozenset({
    "terminar dictado", "salir del dictado", "salir del modo dictado",
    "parar dictado", "parar de dictar", "fin del dictado",
    "modo comando", "volver a comandos",
})
_CLEAR_COMMANDS: frozenset[str] = frozenset({
    "borrar", "borrar todo", "limpiar", "limpiar todo", "清除",
    "borrar texto", "limpiar texto",
})


@dataclass
class DictationState:
    """State for the dictation mode buffer."""

    active: bool = False
    buffer: list[str] = field(default_factory=list)
    last_input_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def activate(self) -> None:
        """Enable dictation mode and clear buffer."""
        with self._lock:
            self.active = True
            self.buffer.clear()
            self.last_input_time = time.monotonic()
            logger.info("dictation mode activated")

    def deactivate(self) -> None:
        """Disable dictation mode and clear buffer."""
        with self._lock:
            self.active = False
            self.buffer.clear()
            logger.info("dictation mode deactivated")

    def add_text(self, text: str) -> None:
        """Add transcribed text to the buffer."""
        with self._lock:
            if not self.active:
                return
            self.buffer.append(text)
            self.last_input_time = time.monotonic()
            logger.debug("dictation buffer: +%r (total: %d)", text, len(self.buffer))

    def get_full_text(self) -> str:
        """Return the accumulated text as a single string."""
        with self._lock:
            return " ".join(self.buffer)

    def clear_buffer(self) -> None:
        """Clear the buffer without sending."""
        with self._lock:
            self.buffer.clear()
            self.last_input_time = time.monotonic()
            logger.debug("dictation buffer cleared")


def type_text(text: str, delay_ms: int = 10) -> bool:
    """Type text into the focused window using xdotool.

    Args:
        text: The text to type.
        delay_ms: Delay between keystrokes in milliseconds.

    Returns:
        True if successful, False otherwise.
    """
    if not text:
        return True

    try:
        # xdotool type handles special characters and Unicode
        result = subprocess.run(
            ["xdotool", "type", "--delay", str(delay_ms), "--clearmodifiers", text],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            logger.error("xdotool type failed: %s", result.stderr)
            return False
        logger.debug("typed %d chars", len(text))
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("xdotool type error: %s", exc)
        return False


def press_enter() -> bool:
    """Press Enter key in the focused window.

    Returns:
        True if successful, False otherwise.
    """
    try:
        result = subprocess.run(
            ["xdotool", "key", "Return"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            logger.error("xdotool key failed: %s", result.stderr)
            return False
        logger.debug("pressed Enter")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("xdotool key error: %s", exc)
        return False


def clear_input_field() -> bool:
    """Clear the current input field (Ctrl+A then Delete).

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Select all then delete
        result = subprocess.run(
            ["xdotool", "key", "ctrl+a", "Delete"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            logger.error("xdotool clear failed: %s", result.stderr)
            return False
        logger.debug("cleared input field")
        return True
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("xdotool clear error: %s", exc)
        return False


class DictationManager:
    """Manages dictation mode: text accumulation, control commands, and injection.

    This is the main interface for the orchestrator to interact with dictation.
    """

    def __init__(self) -> None:
        self.state = DictationState()

    def is_control_command(self, text: str) -> str | None:
        """Check if text is a dictation control command.

        Returns:
            "send" if it's a send command, "exit" if it's an exit command,
            "clear" if it's a clear command, None otherwise.
        """
        normalized = text.strip().lower()

        # Check exact matches first
        if normalized in _SEND_COMMANDS:
            return "send"
        if normalized in _EXIT_COMMANDS:
            return "exit"
        if normalized in _CLEAR_COMMANDS:
            return "clear"

        # Check prefix matches (e.g. "enviar esto" → send)
        for cmd in _SEND_COMMANDS:
            if normalized.startswith(cmd):
                return "send"
        for cmd in _EXIT_COMMANDS:
            if normalized.startswith(cmd):
                return "exit"
        for cmd in _CLEAR_COMMANDS:
            if normalized.startswith(cmd):
                return "clear"

        return None

    def process_transcript(self, text: str) -> tuple[bool, str]:
        """Process a transcribed utterance in dictation mode.

        Args:
            text: The transcribed speech text.

        Returns:
            Tuple of (should_respond, response_text):
            - (True, "enviado") if text was sent
            - (True, "borrado") if buffer was cleared
            - (True, "dictado terminado") if mode was exited
            - (False, "") if text was added to buffer (no response needed)
        """
        if not self.state.active:
            return False, ""

        # Check for control commands
        command = self.is_control_command(text)

        if command == "send":
            full_text = self.state.get_full_text()
            if full_text.strip():
                success = type_text(full_text)
                # Add a small delay, then press Enter
                time.sleep(0.1)
                press_enter()
                self.state.clear_buffer()
                # Deactivate dictation after sending — user can reactivate with "modo dictado"
                self.state.deactivate()
                if success:
                    return True, "enviado"
                else:
                    return True, "error al enviar"
            else:
                return True, "no hay texto para enviar"

        elif command == "exit":
            self.state.deactivate()
            return True, "dictado terminado"

        elif command == "clear":
            self.state.clear_buffer()
            return True, "borrado"

        else:
            # Regular text — add to buffer and type it
            self.state.add_text(text)
            success = type_text(text)
            if not success:
                return True, "error al escribir"
            return False, ""

    def activate(self) -> None:
        """Activate dictation mode."""
        self.state.activate()

    def deactivate(self) -> None:
        """Deactivate dictation mode."""
        self.state.deactivate()

    @property
    def is_active(self) -> bool:
        """Check if dictation mode is active."""
        return self.state.active
