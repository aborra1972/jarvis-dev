"""LLM intent resolution riding the persistent opencode server (PR2, task 2.4).

ADR-2/ADR-8: non-destructive intents resolve through the SAME OpenCode
provider the user already configured — ``opencode run --attach`` with a
JSON-only prompt (zero provider setup). Transport is injectable: tests drive
the FakeProvider; the interpreter only depends on the IntentProvider protocol.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Protocol

from jarvis.interpreter import schema


class IntentProvider(Protocol):
    """Resolve a prompt+system pair into a raw JSON payload (dict)."""

    def resolve(self, prompt: str, system: str) -> dict: ...


class FakeProvider:
    """Canned provider for tests and orchestrator fakes; returns queued payloads."""

    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def resolve(self, prompt: str, system: str) -> dict:
        self.calls.append((prompt, system))
        if not self.responses:
            raise RuntimeError("fake provider exhausted")
        return self.responses.pop(0)


def build_opencode_command(
    server_url: str, session_id: str | None, prompt: str, workdir: str | Path | None = None
) -> list[str]:
    """``opencode run --attach <url> [-s <sessionID>] --format json [--dir <repo>] "<prompt>"`` (ADR-8).

    List-args subprocess (no shell) keeps the prompt/entities inert. PR6
    (integration): ``-s`` is emitted ONLY when a sessionID is known — a fresh
    server rejects unknown sessions with "Session not found", so the first run
    after serve spawns without it and binds the id from the NDJSON stream.
    """
    command = ["opencode", "run", "--attach", server_url]
    if session_id is not None:
        command += ["-s", session_id]
    command += ["--format", "json"]
    if workdir is not None:
        command += ["--dir", str(workdir)]
    command.append(prompt)
    return command


def parse_session_id(output: str) -> str | None:
    """Extract the sessionID from ``opencode run --format json`` NDJSON events."""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        sid = event.get("sessionID")
        if isinstance(sid, str) and sid:
            return sid
    return None


def parse_assistant_text(output: str) -> str:
    """Extract the final assistant text from ``opencode run --format json`` NDJSON events.

    PR6 (verified against opencode 1.18.18): the answer streams as
    ``type:"text"`` events with the text under ``part.text``; older shapes
    (``message.parts[].text`` / ``message.text``) are kept as fallbacks.
    """
    text = ""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "text":
            part = event.get("part") or {}
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text += part["text"]
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        for part in message.get("parts") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                text += part.get("text", "")
        if not text and isinstance(message.get("text"), str):
            text = message["text"]
    return text.strip()


class OpenCodeProvider:
    """Real transport: ``opencode run --attach`` via list-args subprocess (no shell)."""

    def __init__(
        self,
        server_url: str,
        session_id: str | None,
        workdir: str | Path | None = None,
        timeout: float = 30.0,
        runner: object | None = None,
    ) -> None:
        self.server_url = server_url
        self.session_id = session_id
        self.workdir = Path(workdir) if workdir else None
        self.timeout = timeout
        self.runner = runner or subprocess.run

    def resolve(self, prompt: str, system: str) -> dict:
        command = build_opencode_command(
            self.server_url, self.session_id, f"{system}\n\n{prompt}", self.workdir
        )
        result = self.runner(command, capture_output=True, text=True, timeout=self.timeout)
        if result.returncode != 0:
            raise RuntimeError(f"opencode run exited {result.returncode}: {result.stderr[:200]}")
        text = parse_assistant_text(result.stdout)
        if not text:
            raise RuntimeError("opencode run returned no assistant text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"opencode returned non-JSON output: {text[:200]}") from exc


class DirectProvider:
    """Direct transport: ``opencode run`` without server (slower but no dependency)."""

    def __init__(
        self,
        workdir: str | Path | None = None,
        timeout: float = 30.0,
        model: str | None = None,
        runner: object | None = None,
    ) -> None:
        self.workdir = Path(workdir) if workdir else None
        self.timeout = timeout
        self.model = model
        self.runner = runner or subprocess.run

    def resolve(self, prompt: str, system: str) -> dict:
        command = ["opencode", "run", "--format", "json"]
        if self.model:
            command += ["-m", self.model]
        if self.workdir is not None:
            command += ["--dir", str(self.workdir)]
        command.append(f"{system}\n\n{prompt}")
        result = self.runner(command, capture_output=True, text=True, timeout=self.timeout)
        if result.returncode != 0:
            raise RuntimeError(f"opencode run exited {result.returncode}: {result.stderr[:200]}")
        text = parse_assistant_text(result.stdout)
        if not text:
            raise RuntimeError("opencode run returned no assistant text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"opencode returned non-JSON output: {text[:200]}") from exc


def resolve(prompt: str, system: str, provider: IntentProvider) -> schema.Intent:
    """Resolve and validate through the injected provider."""
    payload = provider.resolve(prompt, system)
    return schema.validate(payload)
