"""LLM intent resolution — Ollama direct HTTP (primary) + opencode fallback.

ADR-2/ADR-8: non-destructive intents resolve through a local LLM via
Ollama's HTTP API (localhost:11434). This keeps the entire pipeline offline
and under 5 seconds for voice interaction. The OpenCode transport remains
as a fallback; tests use FakeProvider.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Protocol

from jarvis.interpreter import schema

logger = logging.getLogger("jarvis.llm")


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


class OllamaProvider:
    """Direct HTTP transport to Ollama (localhost:11434) — primary LLM provider.

    ADR-2: Ollama is Jarvis's brain for intent routing. No subprocess, no
    server dependency. Optimized for voice latency: num_ctx=1024,
    num_predict=64 (we only need ~20 tokens for the JSON response),
    temperature=0.1 for deterministic output.
    """

    def __init__(
        self,
        model: str = "qwen2.5:3b",
        base_url: str = "http://localhost:11434",
        timeout: float = 5.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def resolve(self, prompt: str, system: str) -> dict:
        url = f"{self.base_url}/api/generate"
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "num_ctx": 1024,
                "temperature": 0.1,
                "num_predict": 64,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        text = data.get("response", "").strip()
        if not text:
            raise RuntimeError("Ollama returned empty response")

        # Strip markdown code fences: ```json ... ``` → raw JSON
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned non-JSON: {text[:200]}") from exc


class GeminiProvider:
    """Google Gemini API (v1beta) for intent routing — cloud LLM provider.

    Uses the Generative Language REST API with a short timeout for voice
    interaction. Raises RuntimeError on any failure so the caller can fall
    back to the local provider.
    """

    _ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        timeout: float = 5.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def resolve(self, prompt: str, system: str) -> dict:
        url = f"{self._ENDPOINT}/{self.model}:generateContent"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 64,
                "responseMimeType": "application/json",
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:200]
            # 429 = rate limit / quota exhausted → fall back, don't crash
            if exc.code == 429:
                raise RuntimeError(f"Gemini quota exhausted: {body}") from exc
            raise RuntimeError(f"Gemini HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        # Extract text from candidates
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned empty response")

        # Strip markdown code fences: ```json ... ``` → raw JSON
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        text = text.strip()

        # If text still isn't pure JSON, try to extract the JSON object
        if not text.startswith("{"):
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                text = match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini returned non-JSON: {text[:200]}") from exc


class FallbackProvider:
    """Try primary provider first, fall back to secondary on any failure.

    Used for auto mode: Gemini (fast, cloud) → Ollama (local, offline).
    """

    def __init__(self, primary: IntentProvider, secondary: IntentProvider) -> None:
        self._primary = primary
        self._secondary = secondary
        self.last_provider: str = "primary"

    def resolve(self, prompt: str, system: str) -> dict:
        try:
            result = self._primary.resolve(prompt, system)
            self.last_provider = "primary"
            return result
        except Exception as exc:
            logger.warning("Primary provider failed, falling back to secondary: %s", exc)
            result = self._secondary.resolve(prompt, system)
            self.last_provider = "secondary"
            return result


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
