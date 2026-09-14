import pytest

from jarvis import cli
from jarvis.services.spotify import APPROVED_SPOTIFY_SCOPES, spotify_device_fingerprint


def test_spotify_authorize_routes_to_safe_url_constructor(monkeypatch, capsys):
    called = {}

    def fake(configuration, *, transaction, allow_pending_authorization):
        called.update(configuration=configuration, transaction=transaction,
                      allow_pending_authorization=allow_pending_authorization)
        return "https://accounts.spotify.com/authorize?state=secret-state&code_challenge=secret-challenge"

    monkeypatch.setattr(cli, "create_spotify_authorization", fake)
    assert cli.main(["spotify", "authorize"]) == 0
    output = capsys.readouterr().out
    assert "secret-state" not in output
    assert "secret-challenge" not in output
    assert "constructed" in output.lower()
    assert called["transaction"].session_id
    assert called["allow_pending_authorization"] is True


def test_spotify_authorize_does_not_execute_browser_or_callback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "create_spotify_authorization", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "webbrowser", pytest.fail, raising=False)
    assert cli.main(["spotify", "authorize"]) == 1
    assert "autorización" in capsys.readouterr().err.lower()


def test_spotify_live_mode_is_explicit_and_reports_safe_status(monkeypatch, capsys):
    from jarvis.services.spotify import OAuthErrorCode, OAuthResult

    called = {}
    monkeypatch.setattr(cli, "run_spotify_live_authorization", lambda *args, **kwargs: (
        called.update(kwargs=kwargs) or OAuthResult(OAuthErrorCode.NETWORK_TIMEOUT, "timeout")
    ))
    assert cli.main(["spotify", "authorize", "--live"]) == 1
    assert "timeout" in capsys.readouterr().err
    assert callable(called["kwargs"]["browser_opener"])
    assert callable(called["kwargs"]["server_factory"])


@pytest.mark.parametrize("diagnostic", [
    "token_http_400", "token_http_401", "token_http_other",
])
def test_spotify_live_mode_reports_only_token_http_category(
    monkeypatch, capsys, diagnostic,
):
    from jarvis.services.spotify import OAuthErrorCode, OAuthResult

    monkeypatch.setattr(
        cli,
        "run_spotify_live_authorization",
        lambda *args, **kwargs: OAuthResult(
            OAuthErrorCode.PROVIDER_ERROR,
            "unsafe payload error_description=secret-description client_id=secret-client "
            "code=secret-code verifier=secret-verifier state=secret-state "
            "token=secret-token url=https://secret.example/token headers=secret-headers",
            diagnostic=diagnostic,
        ),
    )

    assert cli.main(["spotify", "authorize", "--live"]) == 1
    error = capsys.readouterr().err
    assert error.strip() == f"provider_error: {diagnostic}"
    assert all(secret not in error for secret in (
        "secret-description", "secret-client", "secret-code", "secret-verifier",
        "secret-state", "secret-token", "https://secret.example/token", "secret-headers",
    ))


def test_spotify_live_mode_reports_typed_code_without_sensitive_details(monkeypatch, capsys):
    from jarvis.services.spotify import OAuthErrorCode, OAuthResult

    monkeypatch.setattr(
        cli,
        "run_spotify_live_authorization",
        lambda *args, **kwargs: OAuthResult(
            OAuthErrorCode.PROVIDER_ERROR,
            "safe authorization failure",
            access_token="secret-token",
            payload={"error": "secret-provider-payload"},
        ),
    )

    assert cli.main(["spotify", "authorize", "--live"]) == 1
    error = capsys.readouterr().err
    assert "provider_error" in error
    assert "safe authorization failure" in error
    assert "secret-token" not in error
    assert "secret-provider-payload" not in error


@pytest.mark.parametrize("callback_code", [
    "state_mismatch", "invalid_path", "invalid_query_keys",
    "duplicate_or_empty_query", "fragment_present", "expired", "already_consumed",
])
def test_spotify_live_mode_reports_only_safe_callback_category(monkeypatch, capsys, callback_code):
    from jarvis.services.spotify import OAuthCallbackCode, OAuthErrorCode, OAuthResult

    monkeypatch.setattr(
        cli,
        "run_spotify_live_authorization",
        lambda *args, **kwargs: OAuthResult(
            OAuthErrorCode.INVALID_RESPONSE,
            "http://127.0.0.1:8888/callback?code=secret-code&state=secret-state "
            "verifier=secret-verifier token=secret-token provider=secret-payload",
            callback_code=OAuthCallbackCode(callback_code),
        ),
    )

    assert cli.main(["spotify", "authorize", "--live"]) == 1
    error = capsys.readouterr().err
    assert error.strip() == f"invalid_response: {callback_code}"
    assert all(secret not in error for secret in (
        "http://127.0.0.1:8888/callback", "secret-code", "secret-state",
        "secret-verifier", "secret-token", "secret-payload",
    ))


def test_spotify_live_mode_reports_sanitized_query_key_diagnostic(monkeypatch, capsys):
    from jarvis.services.spotify import OAuthCallbackCode, OAuthErrorCode, OAuthResult

    monkeypatch.setattr(
        cli,
        "run_spotify_live_authorization",
        lambda *args, **kwargs: OAuthResult(
            OAuthErrorCode.INVALID_RESPONSE,
            "unsafe callback URL and values",
            callback_code=OAuthCallbackCode.INVALID_QUERY_KEYS,
            callback_diagnostic="keys:code,state,iss,unknown",
        ),
    )

    assert cli.main(["spotify", "authorize", "--live"]) == 1
    error = capsys.readouterr().err
    assert error.strip() == "invalid_response: keys:code,state,iss,unknown"
    assert "unsafe callback URL" not in error
    assert "https://accounts.spotify.com" not in error
    assert "unknown-attacker-key" not in error


def test_spotify_live_mode_passes_bounded_cli_timeout(monkeypatch):
    from jarvis.services.spotify import OAuthErrorCode, OAuthResult

    called = {}
    monkeypatch.setattr(cli, "run_spotify_live_authorization", lambda *args, **kwargs: (
        called.update(kwargs=kwargs) or OAuthResult(OAuthErrorCode.NETWORK_TIMEOUT, "timeout")
    ))
    assert cli.main(["spotify", "authorize", "--live", "--timeout", "120"]) == 1
    assert called["kwargs"]["timeout_s"] == 120.0


def test_spotify_live_mode_rejects_timeout_above_hard_max(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_spotify_live_authorization", pytest.fail)
    assert cli.main(["spotify", "authorize", "--live", "--timeout", "121"]) == 2
    assert "120" in capsys.readouterr().err


def test_spotify_target_setup_requires_explicit_confirmation_and_writes_hash_only(monkeypatch, capsys):
    raw_id = "provider-secret-id"
    written = []
    class Api:
        def __call__(self, method, url, payload, timeout):
            assert method == "GET" and url.endswith("/me/player/devices")
            return {"devices": [{"id": raw_id, "name": "Desktop", "type": "Computer"}]}
    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": True, "authorized": True}, object(), None))
    monkeypatch.setattr(cli, "_spotify_playback_dependencies", lambda: ({}, lambda: ["spotify"]))
    monkeypatch.setattr(cli, "create_spotify_oauth_client", lambda *a, **k: object())
    monkeypatch.setattr(cli, "SpotifyPlaybackBridge", lambda **k: Api())
    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert cli._handle_spotify_target_setup(writer=written.append) == 0
    assert written == [spotify_device_fingerprint(raw_id)]
    output = capsys.readouterr().out
    assert raw_id not in output


@pytest.mark.parametrize("device_type", ["Smartphone", "Speaker", "COMPUTER", "computerized", "unknown"])
def test_spotify_target_setup_rejects_non_computer_types(monkeypatch, capsys, device_type):
    written = []

    class Api:
        def __call__(self, method, url, payload, timeout):
            return {"devices": [{"id": "provider-id", "name": "Desktop", "type": device_type}]}

    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": True, "authorized": True}, object(), None))
    monkeypatch.setattr(cli, "_spotify_playback_dependencies", lambda: ({}, lambda: ["spotify"]))
    monkeypatch.setattr(cli, "create_spotify_oauth_client", lambda *a, **k: object())
    monkeypatch.setattr(cli, "SpotifyPlaybackBridge", lambda **k: Api())
    monkeypatch.setattr("builtins.input", pytest.fail)

    assert cli._handle_spotify_target_setup(writer=written.append) == 1
    assert written == []
    assert "no valid computer target" in capsys.readouterr().err


def test_existing_setup_spotify_alias_remains_routed(monkeypatch):
    monkeypatch.setattr(cli, "_handle_spotify_setup", lambda: 7)
    assert cli.main(["spotify", "setup"]) == 7


def test_spotify_search_cli_routes_safe_candidates_without_playback(monkeypatch, capsys):
    from jarvis.services.spotify import CatalogBridgeCode, CatalogCandidate, CatalogResult, CatalogCode
    class FakeBridge:
        def __init__(self, **kwargs): self.kwargs = kwargs
        def search(self, kind, query, *, session_id, limit):
            assert (kind, query, session_id, limit) == ("album", "Björk", "cli", 10)
            return type("Result", (), {"code": CatalogBridgeCode.OK, "catalog": CatalogResult(CatalogCode.SINGLE, (CatalogCandidate("opaque", "album", "Vespertine", "spotify:album:raw"),))})()
    monkeypatch.setattr(cli, "SpotifyCatalogBridge", FakeBridge)
    monkeypatch.setattr(cli, "create_spotify_oauth_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": True, "authorized": True}, object(), lambda *a: None))
    assert cli.main(["spotify", "search", "--kind", "album", "--query", "Björk"]) == 0
    output = capsys.readouterr().out
    assert "Vespertine" in output and "album" in output and "opaque" in output
    assert "spotify:album:raw" not in output and "Björk" not in output


def test_spotify_search_and_play_requires_numbered_selection_before_playback(monkeypatch, capsys):
    from jarvis.services.spotify import CatalogBridgeCode, CatalogCandidate, CatalogResult, CatalogCode, PlaybackResult, PlaybackCode
    candidate = CatalogCandidate("opaque", "artist", "Björk", "spotify:artist:raw")
    class FakeBridge:
        def __init__(self, **kwargs): self.catalog = object()
        def search(self, *args, **kwargs):
            return type("Result", (), {"code": CatalogBridgeCode.OK, "catalog": CatalogResult(CatalogCode.MULTIPLE, (candidate, CatalogCandidate("two", "artist", "Other", "spotify:artist:two")))})()
    policy_calls = []
    class Policy:
        def __init__(self, **kwargs): pass
        def play_selection(self, *args, **kwargs):
            policy_calls.append(args); return PlaybackResult(PlaybackCode.OK)
    monkeypatch.setattr(cli, "SpotifyCatalogBridge", FakeBridge)
    monkeypatch.setattr(cli, "PlaybackPolicy", Policy, raising=False)
    monkeypatch.setattr(cli, "SpotifyPlaybackBridge", lambda **kwargs: object())
    monkeypatch.setattr(cli, "create_spotify_oauth_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": True, "authorized": True}, object(), lambda *a: None))
    monkeypatch.setattr(cli, "_spotify_playback_dependencies", lambda: ({"target_fingerprint": "desktop-1"}, lambda: ["spotify"]))
    monkeypatch.setattr("builtins.input", lambda prompt: "2")
    assert cli.main(["spotify", "search-and-play", "--kind", "artist", "--query", "Björk"]) == 0
    assert len(policy_calls) == 1 and policy_calls[0][1] == "two"
    output = capsys.readouterr().out
    assert "spotify:artist" not in output and "opaque" not in output and "Björk" in output


def test_spotify_search_and_play_eof_never_plays(monkeypatch):
    from jarvis.services.spotify import CatalogBridgeCode, CatalogCandidate, CatalogResult, CatalogCode
    class FakeBridge:
        def __init__(self, **kwargs): self.catalog = object()
        def search(self, *args, **kwargs):
            return type("Result", (), {"code": CatalogBridgeCode.OK, "catalog": CatalogResult(CatalogCode.SINGLE, (CatalogCandidate("one", "album", "Safe", "spotify:album:raw"),))})()
    monkeypatch.setattr(cli, "SpotifyCatalogBridge", FakeBridge)
    monkeypatch.setattr(cli, "create_spotify_oauth_client", lambda *args, **kwargs: object())
    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": True, "authorized": True}, object(), lambda *a: None))
    monkeypatch.setattr(cli, "_spotify_playback_dependencies", lambda: ({"target_fingerprint": "desktop-1"}, lambda: ["spotify"]))
    monkeypatch.setattr("builtins.input", lambda prompt: (_ for _ in ()).throw(EOFError))
    monkeypatch.setattr(cli, "PlaybackPolicy", pytest.fail, raising=False)
    assert cli.main(["spotify", "search-and-play", "--kind", "album", "--query", "Safe"]) == 1


def test_spotify_search_cli_disabled_does_not_construct_or_transport(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_spotify_search_dependencies", lambda: ({"enabled": False, "authorized": False}, object(), pytest.fail))
    monkeypatch.setattr(cli, "create_spotify_oauth_client", pytest.fail)
    assert cli.main(["spotify", "search", "--kind", "artist", "--query", "secret-query"]) == 1
    assert "secret-query" not in capsys.readouterr().err
