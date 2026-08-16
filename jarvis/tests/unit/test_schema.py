"""Intent schema tests (PR2, task 2.4).

The interpreter only emits the 15-command allowlist (5 domains); schema
validation is pure and table-driven. Entity validation encodes the design
threat matrix (repo metachars, disallowed app, malformed URL).
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.schema import (
    ALLOWED_INTENTS,
    CONFIDENCE_THRESHOLD,
    DESTRUCTIVE_INTENTS,
    DOMAIN_INTENTS,
    INTENT_DOMAIN,
    SchemaError,
    build_system_prompt,
    validate,
    validate_entities,
)
from jarvis.interpreter.schema import Intent


# --- allowlist shape ---------------------------------------------------------
def test_16_commands_in_5_domains() -> None:
    commands = ALLOWED_INTENTS - {"unknown"}
    assert len(commands) == 16
    assert sum(len(v) for v in DOMAIN_INTENTS.values()) == 16
    assert set(DOMAIN_INTENTS) == {"opencode", "system", "files", "web", "lifecycle"}


def test_destructive_intents_are_gated() -> None:
    assert DESTRUCTIVE_INTENTS == {"shutdown", "reboot", "power_off_self"}
    assert DESTRUCTIVE_INTENTS <= ALLOWED_INTENTS
    assert INTENT_DOMAIN["shutdown"] == "system"
    assert INTENT_DOMAIN["power_off_self"] == "lifecycle"
    assert CONFIDENCE_THRESHOLD == 0.6


# --- validate: happy path ----------------------------------------------------
VALID_PAYLOADS: list[tuple[dict, str]] = [
    ({"intent": "ask", "entities": {"query": "como funciona auth"}, "confidence": 0.9}, "ask"),
    ({"intent": "open_repo", "entities": {"repo": "anubis-api"}, "confidence": 0.8}, "open_repo"),
    # empty repo = active project delegation (orchestrator PR3)
    ({"intent": "open_repo", "entities": {"repo": ""}, "confidence": 0.8}, "open_repo"),
    ({"intent": "create_doc", "entities": {"text": "resumen del sprint"}, "confidence": 0.95}, "create_doc"),
    ({"intent": "open_url", "entities": {"url": "https://github.com/x"}, "confidence": 0.7}, "open_url"),
    ({"intent": "web_search", "entities": {"query": "tal libreria"}, "confidence": 0.6}, "web_search"),
    ({"intent": "unknown", "entities": {}, "confidence": 0.9}, "unknown"),
    # confidence coerced: int ok, missing → 0.0
    ({"intent": "help", "entities": {}, "confidence": 1}, "help"),
    ({"intent": "ask", "entities": {"query": "x"}}, "ask"),
]


@pytest.mark.parametrize(("payload", "expected"), VALID_PAYLOADS)
def test_validate_accepts(payload: dict, expected: str) -> None:
    intent = validate(payload)
    assert intent.intent == expected
    assert 0.0 <= intent.confidence <= 1.0
    assert isinstance(intent.entities, dict)


# --- validate: rejection -----------------------------------------------------
INVALID_PAYLOADS: list[tuple[dict, str]] = [
    ({"intent": "delete_files", "entities": {}, "confidence": 0.9}, "unknown_intent"),
    ({"intent": "ask", "entities": {}, "confidence": 0.9}, "missing_entity"),
    ({"intent": "ask", "entities": {"query": "x"}, "confidence": 2.0}, "bad_confidence"),
    ({"intent": "ask", "entities": {"query": "x"}, "confidence": -0.1}, "bad_confidence"),
    ({"intent": "ask", "entities": {"query": "x"}, "confidence": "high"}, "bad_confidence"),
    ({"intent": "ask", "entities": {"query": ["x"]}, "confidence": 0.9}, "bad_entities"),
    ("not a dict", "bad_payload"),
]


@pytest.mark.parametrize(("payload", "code"), INVALID_PAYLOADS)
def test_validate_rejects(payload: dict, code: str) -> None:
    with pytest.raises(SchemaError) as exc:
        validate(payload)
    assert exc.value.code == code


# --- entity validation (threat matrix) --------------------------------------
def test_repo_entity_rejects_shell_metachars() -> None:
    intent = Intent(intent="open_repo", entities={"repo": '";rm -rf /"'}, confidence=0.9)
    assert validate_entities(intent) == ["repo"]


def test_repo_entity_rejects_leading_dash() -> None:
    intent = Intent(intent="open_repo", entities={"repo": "-rf"}, confidence=0.9)
    assert validate_entities(intent) == ["repo"]


def test_repo_entity_accepts_clean_name() -> None:
    intent = Intent(intent="open_repo", entities={"repo": "anubis-api"}, confidence=0.9)
    assert validate_entities(intent) == []


def test_repo_entity_accepts_empty_when_active_project() -> None:
    intent = Intent(intent="open_repo", entities={"repo": ""}, confidence=0.9, use_active_project=True)
    assert validate_entities(intent) == []


def test_app_entity_rejects_disallowed_app() -> None:
    intent = Intent(intent="open_app", entities={"app": "chrome"}, confidence=0.9)
    assert validate_entities(intent, app_allowlist={"firefox"}) == ["app"]


def test_app_entity_accepts_allowlisted_app() -> None:
    intent = Intent(intent="open_app", entities={"app": "firefox"}, confidence=0.9)
    assert validate_entities(intent, app_allowlist={"firefox"}) == []


def test_url_entity_rejects_malformed_url() -> None:
    intent = Intent(intent="open_url", entities={"url": "no es una url"}, confidence=0.9)
    assert validate_entities(intent) == ["url"]


def test_url_entity_rejects_non_http_scheme() -> None:
    intent = Intent(intent="open_url", entities={"url": "ftp://github.com/x"}, confidence=0.9)
    assert validate_entities(intent) == ["url"]


def test_url_entity_accepts_http_https() -> None:
    for url in ("https://github.com/x", "http://localhost:8000"):
        intent = Intent(intent="open_url", entities={"url": url}, confidence=0.9)
        assert validate_entities(intent) == []


# --- system prompt -----------------------------------------------------------
def test_system_prompt_lists_all_commands_and_domains() -> None:
    prompt = build_system_prompt()
    assert "JSON" in prompt
    for intent in ALLOWED_INTENTS:
        assert intent in prompt
    for domain in DOMAIN_INTENTS:
        assert domain in prompt
