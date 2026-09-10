"""Codex reasoning-effort configuration tests."""

import pytest

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


def test_spotify_local_config_defaults_disabled_and_safe() -> None:
    values = config.load_spotify_local_config({})
    assert values == {"enabled": False, "playerctl_bin": "playerctl", "identity": "spotify", "timeout_s": 2.0}


def test_spotify_local_config_accepts_valid_explicit_values() -> None:
    values = config.load_spotify_local_config({
        "SPOTIFY_LOCAL_ENABLED": "true",
        "SPOTIFY_PLAYERCTL_BIN": "/usr/bin/playerctl",
        "SPOTIFY_MPRIS_IDENTITY": "spotify.desktop",
        "SPOTIFY_LOCAL_TIMEOUT_S": "4.5",
    })
    assert values == {"enabled": True, "playerctl_bin": "/usr/bin/playerctl", "identity": "spotify.desktop", "timeout_s": 4.5}


@pytest.mark.parametrize("key_value", [
    ("SPOTIFY_PLAYERCTL_BIN", "playerctl;rm -rf /"),
    ("SPOTIFY_MPRIS_IDENTITY", "other player"),
    ("SPOTIFY_LOCAL_TIMEOUT_S", "0"),
    ("SPOTIFY_LOCAL_TIMEOUT_S", "not-a-number"),
])
def test_spotify_local_config_invalid_values_fail_closed(key_value: tuple[str, str]) -> None:
    values = config.load_spotify_local_config({"SPOTIFY_LOCAL_ENABLED": "true", key_value[0]: key_value[1]})
    assert values["enabled"] is False
