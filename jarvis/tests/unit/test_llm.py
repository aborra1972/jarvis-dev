"""LLM intent resolution tests (PR2, task 2.4).

Transport is injectable: tests drive the FakeProvider; the interpreter only
depends on the IntentProvider protocol. OpenCodeProvider is exercised at the
pure boundaries (command builder + NDJSON event parser); the real
serve/attach round-trip is integration scope (PR4, -m slow).
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.llm import (
    FakeProvider,
    OpenCodeProvider,
    build_opencode_command,
    parse_assistant_text,
    parse_session_id,
    resolve,
)
from jarvis.interpreter.schema import SchemaError


# --- build_opencode_command (ADR-8: opencode run --attach) -------------------
def test_command_builds_attach_with_session_and_json_format() -> None:
    command = build_opencode_command("http://127.0.0.1:32111", "interp-1", "abrir firefox")
    assert command == [
        "opencode", "run", "--attach", "http://127.0.0.1:32111",
        "-s", "interp-1", "--format", "json", "abrir firefox",
    ]


def test_command_omits_session_flag_when_session_is_none() -> None:
    # PR6 (integration): a fresh server has no registered session, so the first
    # call must NOT pass `-s` (opencode answers "Session not found" otherwise).
    command = build_opencode_command("http://127.0.0.1:32111", None, "abrir firefox")
    assert "-s" not in command
    assert command[command.index("--format") + 1] == "json"


def test_command_includes_dir_when_workdir_given() -> None:
    command = build_opencode_command("http://127.0.0.1:32111", "interp-1", "p", workdir="/tmp/repo")
    assert "--dir" in command
    assert command[command.index("--dir") + 1] == "/tmp/repo"


# --- parse_assistant_text (opencode --format json NDJSON events) -------------
def test_parse_assistant_text_joins_text_parts() -> None:
    output = "\n".join([
        '{"type":"message","message":{"role":"user","parts":[{"type":"text","text":"hola"}]}}',
        '{"type":"message","message":{"role":"assistant","parts":[{"type":"text","text":"{\\"intent\\": \\"ask\\""},{"type":"text","text":", \\"entities\\": {}}"}]}}',
        "",
    ])
    assert parse_assistant_text(output) == '{"intent": "ask", "entities": {}}'


def test_parse_assistant_text_ignores_non_assistant_and_garbage() -> None:
    output = "\n".join([
        "not json at all",
        '{"type":"session.updated","session":{}}',
        '{"type":"message","message":{"role":"user","parts":[{"type":"text","text":"x"}]}}',
    ])
    assert parse_assistant_text(output) == ""


def test_parse_assistant_text_falls_back_to_message_text() -> None:
    output = '{"type":"message","message":{"role":"assistant","text":"{\\"intent\\": \\"help\\"}"}}'
    assert parse_assistant_text(output) == '{"intent": "help"}'


# --- parse_session_id (PR6: bind the server-created session for reuse) --------
def test_parse_session_id_extracts_from_step_events() -> None:
    output = "\n".join([
        '{"type":"step_start","timestamp":1,"sessionID":"ses_abc123","part":{}}',
        '{"type":"text","timestamp":2,"sessionID":"ses_abc123","part":{}}',
    ])
    assert parse_session_id(output) == "ses_abc123"


def test_parse_session_id_returns_none_when_absent() -> None:
    assert parse_session_id('{"type":"done"}') is None
    assert parse_session_id("") is None
    assert parse_session_id("not json") is None


# --- FakeProvider ------------------------------------------------------------
def test_fake_provider_returns_queued_payloads_in_order() -> None:
    provider = FakeProvider([
        {"intent": "ask", "entities": {"query": "x"}, "confidence": 0.9},
        {"intent": "help", "entities": {}, "confidence": 0.9},
    ])
    first = provider.resolve("p1", "sys")
    second = provider.resolve("p2", "sys")
    assert first["intent"] == "ask"
    assert second["intent"] == "help"
    assert [call[0] for call in provider.calls] == ["p1", "p2"]


# --- resolve() ------------------------------------------------------------------
def test_resolve_returns_validated_intent() -> None:
    provider = FakeProvider([{"intent": "ask", "entities": {"query": "como funciona auth"}, "confidence": 0.9}])
    intent = resolve("preguntar como funciona auth", "system", provider)
    assert intent.intent == "ask"
    assert intent.entities == {"query": "como funciona auth"}
    assert intent.confidence == 0.9


def test_resolve_rejects_off_allowlist_intent() -> None:
    provider = FakeProvider([{"intent": "delete_files", "entities": {}, "confidence": 0.9}])
    with pytest.raises(SchemaError) as exc:
        resolve("borrar todos los archivos", "system", provider)
    assert exc.value.code == "unknown_intent"


# --- OpenCodeProvider: failure paths (pure, no real server) -------------------
def test_open_code_provider_fails_on_nonzero_exit() -> None:
    class FailingRunner:
        def __call__(self, command, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "boom"
            return Result()

    provider = OpenCodeProvider("http://127.0.0.1:32111", "interp-1", runner=FailingRunner())
    with pytest.raises(RuntimeError, match="boom"):
        provider.resolve("p", "sys")


def test_open_code_provider_fails_on_non_json_output() -> None:
    class TextRunner:
        def __call__(self, command, **kwargs):
            class Result:
                returncode = 0
                stdout = '{"type":"message","message":{"role":"assistant","parts":[{"type":"text","text":"hola"}]}}'
                stderr = ""
            return Result()

    provider = OpenCodeProvider("http://127.0.0.1:32111", "interp-1", runner=TextRunner())
    with pytest.raises(RuntimeError, match="non-JSON"):
        provider.resolve("p", "sys")
