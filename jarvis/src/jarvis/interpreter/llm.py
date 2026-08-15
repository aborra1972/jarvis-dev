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
    server_url: str, session_id: str, prompt: str, workdir: str | Path | None = None
) -> list[str]:
    """``opencode run --attach <url> -s <sessionID> --format json [--dir <repo>] "<prompt>"`` (ADR-8).

    List-args subprocess (no shell) keeps the prompt/entities inert.
    """
    command = ["opencode", "run", "--attach", server_url, "-s", session_id, "--format", "json"]
    if workdir is not None:
        command += ["--dir", str(workdir)]
    command.append(prompt)
    return command


def parse_assistant_text(output: str) -> str:
    """Extract the final assistant text from ``opencode run --format json`` NDJSON events."""
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = event.get("message") or {}
        if message.get("role") != "assistant":
            continue
        text = ""
        for part in message.get("parts") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                text += part.get("text", "")
        if not text and isinstance(message.get("text"), str):
            text = message["text"]
        if text.strip():
            return text.strip()
    return ""


class OpenCodeProvider:
    """Real transport: ``opencode run --attach`` via list-args subprocess (no shell)."""

    def __init__(
        self,
        server_url: str,
        session_id: str,
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


def resolve(prompt: str, system: str, provider: IntentProvider) -> schema.Intent:
    """Resolve and validate through the injected provider."""
    payload = provider.resolve(prompt, system)
    return schema.validate(payload)
