"""Agent/persona selection: jarvis | friday | karen.

The setup switch lives in config (AGENT_PROFILES + JARVIS_AGENT env or repo
.env). These tests pin the three profiles, the env override, the invalid-value
fallback, and the derived EDGE_VOICE.
"""

from __future__ import annotations

import pytest

from jarvis import config


def test_agent_profiles_have_exactly_three_expected_keys() -> None:
    assert set(config.AGENT_PROFILES) == {"jarvis", "friday", "karen"}


def test_agent_profiles_are_complete() -> None:
    for key, profile in config.AGENT_PROFILES.items():
        assert profile["name"], key
        assert profile["voice"].endswith("MultilingualNeural"), key
        assert profile["rate"], key
        assert profile["pitch"], key
        assert profile["address"], key
        assert profile["announcement"], key
        assert profile["personality"], key


def test_agent_profiles_voices_match_spec() -> None:
    assert config.AGENT_PROFILES["jarvis"]["voice"] == "en-US-AndrewMultilingualNeural"
    assert config.AGENT_PROFILES["friday"]["voice"] == "en-US-AvaMultilingualNeural"
    assert config.AGENT_PROFILES["karen"]["voice"] == "en-US-EmmaMultilingualNeural"


def test_default_agent_is_jarvis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JARVIS_AGENT", raising=False)
    assert config.agent_name() == "Jarvis"
    assert config.agent_address() == "señor"


def test_env_override_selects_friday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "friday")
    assert config.active_agent() == config.AGENT_PROFILES["friday"]
    assert config.agent_name() == "Friday"
    assert config.agent_voice() == "en-US-AvaMultilingualNeural"
    assert config.agent_rate() == "+5%"
    assert config.agent_pitch() == "+0Hz"


def test_env_override_selects_karen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "karen")
    assert config.agent_name() == "Karen"
    assert config.agent_voice() == "en-US-EmmaMultilingualNeural"
    assert config.agent_rate() == "+3%"
    assert config.agent_pitch() == "+5Hz"


def test_invalid_agent_env_falls_back_to_jarvis_with_warning(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "hal9000")
    assert config.agent_name() == "Jarvis"
    assert "hal9000" in capsys.readouterr().err


def test_jarvis_profile_keeps_exact_address_and_announcement() -> None:
    assert config.AGENT_PROFILES["jarvis"]["address"] == "señor"
    assert (
        config.AGENT_PROFILES["jarvis"]["announcement"]
        == "Buen día, señor. Soy Jarvis, a su servicio."
    )


def test_edge_voice_derives_from_selected_agent() -> None:
    # Definitional: the runtime voice follows the agent selected at import.
    assert config.EDGE_VOICE == config.AGENT_PROFILES[config.AGENT]["voice"]
    assert config.EDGE_RATE == config.AGENT_PROFILES[config.AGENT]["rate"]
    assert config.EDGE_PITCH == config.AGENT_PROFILES[config.AGENT]["pitch"]


def test_agent_announcement_follows_active_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "karen")
    assert config.agent_announcement() == config.AGENT_PROFILES["karen"]["announcement"]
