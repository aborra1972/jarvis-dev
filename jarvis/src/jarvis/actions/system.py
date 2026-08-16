"""System executor (PR4, task 4.4): shutdown/reboot via systemctl, open_app allowlisted.

Design (RF-8, threat matrix): destructive actions run behind the orchestrator's
15s confirm gate and are logged here; open_app only ever spawns xdg-open with
an allowlisted app (disallowed app => rejected, nothing spawned). All
subprocess is list-args via base.safe_run (no shell).
"""

from __future__ import annotations

from jarvis import config
from jarvis.actions import base
from jarvis.interpreter import schema
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult

# User-friendly names → actual command/bin names.
# xdg-open only works with .desktop files or URLs, not app aliases.
_APP_COMMANDS: dict[str, str] = {
    "terminal": "gnome-terminal",
    "explorador": "nemo",
    "navegador": "firefox",
    "nemo": "nemo",
    "nautilus": "nautilus",
    "libreoffice": "libreoffice",
    "code": "code",
    "codium": "codium",
    "vim": "gnome-terminal",
    "nano": "gnome-terminal",
    "htop": "gnome-terminal",
    "opencode": "opencode",
}


def _run(name: str, command: list[str], ok_spoken: str, fail_spoken: str) -> ActionResult:
    base.log(name)
    code, _ = base.safe_run(command)
    if code != 0:
        return ActionResult(ok=False, spoken=fail_spoken)
    return ActionResult(ok=True, spoken=ok_spoken)


def shutdown(intent: Intent, session: object) -> ActionResult:
    return _run("shutdown", ["systemctl", "poweroff"], "Apagando el sistema, señor.", "Lo lamento, señor, no pude apagar el sistema.")


def reboot(intent: Intent, session: object) -> ActionResult:
    return _run("reboot", ["systemctl", "reboot"], "Reiniciando el sistema, señor.", "Lo lamento, señor, no pude reiniciar el sistema.")


def open_app(intent: Intent, session: object) -> ActionResult:
    app = intent.entities.get("app", "")
    if schema.validate_entities(intent, config.ALLOWED_APPS):
        return ActionResult(ok=False, spoken="Esa aplicación no está permitida, señor.")
    # Resolve friendly name to actual command
    command = _APP_COMMANDS.get(app, app)
    code, _ = base.safe_run([command])
    if code != 0:
        return ActionResult(ok=False, spoken="Lo lamento, señor, no pude abrir esa aplicación.")
    return ActionResult(ok=True, spoken=f"Abriendo {app}, señor.")
