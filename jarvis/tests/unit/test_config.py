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


def test_spotify_oauth_config_is_disabled_by_default_with_fixed_policy(monkeypatch) -> None:
    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: pytest.fail("keyring must not be read while disabled"))
    values = config.load_spotify_oauth_config({})
    assert values == {
        "enabled": False,
        "authorized": False,
        "client_id": None,
        "transaction_ttl_s": 300.0,
        "scopes": frozenset({"user-read-playback-state", "user-modify-playback-state"}),
    }


def test_spotify_oauth_config_requires_explicit_enable_and_keyring_id(monkeypatch) -> None:
    assert config.load_spotify_oauth_config({"SPOTIFY_CLIENT_ID": "client"})["enabled"] is False
    assert config.load_spotify_oauth_config({"SPOTIFY_API_ENABLED": "true"})["enabled"] is False
    client_id = "a" * 32

    class Result:
        status = type("Status", (), {"value": "ok"})()
        value = client_id

    class Store:
        def load(self):
            return Result()

    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: Store())
    values = config.load_spotify_oauth_config({
        "SPOTIFY_API_ENABLED": "true", "SPOTIFY_AUTHORIZED": "true",
        "SPOTIFY_CLIENT_ID": "ignored", "SPOTIFY_OAUTH_TRANSACTION_TTL_S": "120",
    })
    assert values["enabled"] is True
    assert values["authorized"] is True
    assert values["client_id"] == client_id
    assert values["transaction_ttl_s"] == 120.0


def test_spotify_oauth_config_loads_pending_authorization_from_keyring(monkeypatch) -> None:
    client_id = "b" * 32

    class Result:
        status = type("Status", (), {"value": "ok"})()
        value = client_id

    class Store:
        def load(self):
            return Result()

    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: Store())
    values = config.load_spotify_oauth_config({
        "SPOTIFY_API_ENABLED": "true", "SPOTIFY_AUTHORIZED": "false",
        "SPOTIFY_OAUTH_TRANSACTION_TTL_S": "90",
    })
    assert values == {
        "enabled": True,
        "authorized": False,
        "client_id": client_id,
        "transaction_ttl_s": 90.0,
        "scopes": frozenset({"user-read-playback-state", "user-modify-playback-state"}),
    }


def test_spotify_oauth_config_declined_or_missing_authorization_still_requires_valid_client_id(monkeypatch) -> None:
    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: pytest.fail("keyring must not be read"))
    for authorization in (None, "declined"):
        environ = {"SPOTIFY_API_ENABLED": "true"}
        if authorization is not None:
            environ["SPOTIFY_AUTHORIZED"] = authorization
        values = config.load_spotify_oauth_config(environ)
        assert values["enabled"] is False
        assert values["authorized"] is False
        assert values["client_id"] is None


def test_spotify_oauth_config_rejects_invalid_values_fail_closed() -> None:
    values = config.load_spotify_oauth_config({
        "SPOTIFY_API_ENABLED": "true",
        "SPOTIFY_CLIENT_ID": "client id",
        "SPOTIFY_OAUTH_TRANSACTION_TTL_S": "0",
    })
    assert values["enabled"] is False
    assert values["client_id"] is None


def test_spotify_oauth_config_recovers_client_id_from_keyring(monkeypatch) -> None:
    client_id = "a" * 32

    class Result:
        status = type("Status", (), {"value": "ok"})()
        value = client_id

    class Store:
        def load(self):
            return Result()

    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: Store())
    values = config.load_spotify_oauth_config({"SPOTIFY_API_ENABLED": "true", "SPOTIFY_AUTHORIZED": "true"})
    assert values["enabled"] is True
    assert values["client_id"] == client_id


@pytest.mark.parametrize("status", ["invalid", "storage_unavailable"])
def test_spotify_oauth_config_keyring_failures_remain_fail_closed(monkeypatch, status) -> None:
    client_id = "c" * 32

    result = type(
        "Result",
        (),
        {"status": type("Status", (), {"value": status})(), "value": client_id},
    )()

    class Store:
        def load(self):
            return result

    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: Store())
    values = config.load_spotify_oauth_config({"SPOTIFY_API_ENABLED": "true", "SPOTIFY_AUTHORIZED": "true"})
    assert values["enabled"] is False
    assert values["client_id"] is None


def test_spotify_oauth_config_does_not_accept_environment_client_id(monkeypatch) -> None:
    monkeypatch.setattr(config, "_spotify_client_id_store", lambda: pytest.fail("authorization is required before keyring"))
    values = config.load_spotify_oauth_config({"SPOTIFY_API_ENABLED": "true", "SPOTIFY_CLIENT_ID": "b" * 32})
    assert values["enabled"] is False
    assert values["client_id"] is None
