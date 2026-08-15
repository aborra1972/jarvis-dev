"""Executor protocol + registry (PR4, task 4.1).

Design "Interfaces / Contracts": executors are in-process modules registered
by intent and dispatched from the orchestrator loop (PR3) via
``execute(intent, session)``. Executors never receive raw transcripts — only
validated intents + entities. Shared subprocess/fs/log helpers keep every
executor shell-free by construction (threat matrix: no arbitrary shell).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult

Handler = Callable[[Intent, object], ActionResult]

_logger = logging.getLogger("jarvis.actions")


def log(event: str) -> None:
    """Audit log for safety-critical actions (shutdown/reboot/power_off_self)."""
    _logger.info(event)


def safe_run(command: list[str], timeout: float = 20.0) -> tuple[int, str]:
    """Run a list-args command (never a shell); returns (returncode, stderr).

    Never raises: missing binaries (OSError) and timeouts surface as a non-zero
    return code so executors degrade to a spoken error (M4).
    """
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stderr.strip()
    except (OSError, subprocess.SubprocessError):
        return 1, "no se pudo ejecutar"


def exclusive_write(path: Path, content: str) -> None:
    """Create a file exclusively (O_EXCL): never overwrites an existing one."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def atomic_write(path: Path, content: str) -> None:
    """Write via temp + rename (atomic; configure's AGENTS.md target)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


class Registry:
    """Intent → handler map with dispatch; unknown intents answer unsupported."""

    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}
        # Verify fix: intents the executor estimates over 3s; the loop speaks a
        # spoken ack before executing them (voice-pipeline "Long LLM operation").
        self.long_running_intents: frozenset[str] = frozenset()

    def register(self, intent: str, handler: Handler) -> None:
        self._handlers[intent] = handler

    def execute(self, intent: Intent, session: object) -> ActionResult:
        handler = self._handlers.get(intent.intent)
        if handler is None:
            return ActionResult(ok=False, spoken="no sé hacer eso todavía")
        return handler(intent, session)

    def handlers(self) -> dict[str, Handler]:
        return dict(self._handlers)


def build_registry() -> Registry:
    """Wire every executor handler (5 domains, 15 intents) into one registry."""
    from jarvis.actions import assistant_lifecycle, files, opencode, system, web

    registry = Registry()
    oc = opencode.OpenCodeExecutor()
    registry.long_running_intents = opencode.LONG_RUNNING_INTENTS
    for intent in opencode.OPCODE_INTENTS:
        registry.register(intent, getattr(oc, f"handle_{intent}"))
    registry.register("shutdown", system.shutdown)
    registry.register("reboot", system.reboot)
    registry.register("open_app", system.open_app)
    registry.register("create_doc", files.create_doc)
    registry.register("open_file_dir", files.open_file_dir)
    registry.register("web_search", web.web_search)
    registry.register("open_url", web.open_url)
    registry.register("power_off_self", assistant_lifecycle.power_off_self)
    registry.register("help", assistant_lifecycle.handle_help)
    return registry
