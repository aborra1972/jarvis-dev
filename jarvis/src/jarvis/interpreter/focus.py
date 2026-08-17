"""Window focus detection for intent routing.

Detects which application currently has keyboard focus using xdotool (X11).
Used by the interpreter to route general questions through OpenCode when a
code editor is focused, or answer directly via LLM otherwise.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("jarvis.interpreter")

# Apps that should route through OpenCode (not direct LLM)
_CODE_EDITORS: frozenset[str] = frozenset({
    "opencode", "code", "codium", "visual studio code", "vscode",
    "vim", "nvim", "nano", "emacs", "sublime", "atom",
    "intellij", "pycharm", "android studio",
    "terminal", "gnome-terminal", "konsole", "alacritty", "kitty", "wezterm",
    "htop", "btop", "bottom",
})


def get_focused_app() -> str:
    """Return the name of the currently focused window (lowercase).

    Uses xdotool to query the active window on X11. Returns empty string
    on failure (Wayland, missing xdotool, no window manager).
    """
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True, text=True, timeout=1,
        )
        if result.returncode == 0:
            return result.stdout.strip().lower()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("xdotool failed: %s", exc)
    return ""


def is_code_editor_focused(focused_app: str | None = None) -> bool:
    """Check if a code editor or terminal has keyboard focus.

    Args:
        focused_app: Optional pre-fetched app name. If None, calls get_focused_app().

    Returns:
        True if a code editor/terminal is focused, False otherwise.
    """
    if focused_app is None:
        focused_app = get_focused_app()
    if not focused_app:
        return False
    return any(editor in focused_app for editor in _CODE_EDITORS)
