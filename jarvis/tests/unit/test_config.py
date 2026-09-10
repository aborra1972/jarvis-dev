"""Codex reasoning-effort configuration tests."""

from jarvis import config


def test_codex_reasoning_effort_defaults_to_low() -> None:
    assert config._resolve_codex_reasoning_effort(None) == "low"
    assert config.CODEX_REASONING_EFFORT == "low"


def test_codex_reasoning_effort_accepts_only_documented_values() -> None:
    assert config.CODEX_REASONING_EFFORTS == {"low", "medium", "high"}
    for effort in config.CODEX_REASONING_EFFORTS:
        assert config._resolve_codex_reasoning_effort(effort) == effort


def test_codex_reasoning_effort_invalid_input_fails_closed_to_low() -> None:
    assert config._resolve_codex_reasoning_effort("invalid") == "low"
    assert config._resolve_codex_reasoning_effort("") == "low"
