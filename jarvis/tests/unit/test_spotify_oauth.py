import base64
import hashlib

import pytest

from jarvis.services.spotify import (
    APPROVED_SPOTIFY_SCOPES,
    CredentialStatus,
    KeyringCredentialStore,
    create_pkce_transaction,
)


def test_pkce_transaction_uses_s256_and_binds_session() -> None:
    tx = create_pkce_transaction("session-1", now=100.0, ttl_s=60.0, token_factory=lambda: "v" * 43)
    assert len(tx.state) >= 32
    assert tx.code_challenge == base64.urlsafe_b64encode(
        hashlib.sha256(tx.verifier.encode()).digest()
    ).rstrip(b"=").decode()
    assert tx.valid_for("session-1", now=159.9)
    assert not tx.valid_for("other-session", now=100.0)


def test_pkce_transaction_expires_and_is_one_time() -> None:
    tx = create_pkce_transaction("session-1", now=100.0, ttl_s=60.0, token_factory=lambda: "x" * 43)
    assert not tx.valid_for("session-1", now=160.0)
    assert not tx.consume("session-1", now=160.0)


def test_pkce_transaction_consumes_once() -> None:
    tx = create_pkce_transaction("session-1", now=100.0, ttl_s=60.0, token_factory=lambda: "x" * 43)
    assert tx.consume("session-1", now=101.0)
    assert not tx.consume("session-1", now=102.0)


def test_approved_scopes_are_fixed() -> None:
    assert APPROVED_SPOTIFY_SCOPES == frozenset({"user-read-playback-state", "user-modify-playback-state"})


def test_keyring_store_round_trip_and_delete() -> None:
    values: dict[str, str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))

        def set_password(self, service, username, value):
            values[(service, username)] = value

        def delete_password(self, service, username):
            values.pop((service, username), None)

    store = KeyringCredentialStore(backend=Backend(), service="jarvis.spotify", username="oauth")
    assert store.save('{"access_token":"secret"}').status is CredentialStatus.OK
    assert store.load().value == '{"access_token":"secret"}'
    assert store.delete().status is CredentialStatus.OK
    assert store.load().status is CredentialStatus.MISSING


def test_keyring_failure_is_storage_unavailable_without_fallback() -> None:
    class Broken:
        def get_password(self, service, username):
            raise RuntimeError("keyring down")

        def set_password(self, service, username, value):
            raise RuntimeError("keyring down")

        def delete_password(self, service, username):
            raise RuntimeError("keyring down")

    store = KeyringCredentialStore(backend=Broken())
    assert store.load().status is CredentialStatus.STORAGE_UNAVAILABLE
    assert store.save("secret").status is CredentialStatus.STORAGE_UNAVAILABLE
    assert store.delete().status is CredentialStatus.STORAGE_UNAVAILABLE
    assert not any("secret" in value for value in store.__dict__.values() if isinstance(value, str))


def test_exchange_uses_pkce_scopes_and_bounded_transport() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    calls = []
    store = _MemoryTokenStore()
    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "v" * 43)

    def transport(method, url, data, headers, timeout):
        calls.append((method, url, data, headers, timeout))
        return _Response(200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600, "scope": "user-read-playback-state user-modify-playback-state"})

    client = OAuthClient(enabled=True, client_id="client", store=store, transport=transport, clock=lambda: 100.0, timeout_s=3.0)
    result = client.exchange_code(tx, "code", session_id="session-1")
    assert result.ok and result.access_token == "access"
    assert calls[0][0:2] == ("POST", "https://accounts.spotify.com/api/token")
    assert calls[0][4] == 3.0
    assert calls[0][2]["grant_type"] == "authorization_code"
    assert calls[0][2]["code_verifier"] == "v" * 43
    assert calls[0][2]["scope"] == "user-modify-playback-state user-read-playback-state"
    assert "access" not in repr(result) and "code" not in repr(result)


def test_refresh_is_single_flight_and_rotates_refresh_token() -> None:
    from jarvis.services.spotify import OAuthClient

    store = _MemoryTokenStore({"access_token": "old", "refresh_token": "r1", "expires_at": 101.0, "scope": list(APPROVED_SPOTIFY_SCOPES)})
    calls = []

    def transport(*args):
        calls.append(args)
        return _Response(200, {"access_token": "new", "refresh_token": "r2", "expires_in": 3600})

    client = OAuthClient(enabled=True, client_id="client", store=store, transport=transport, clock=lambda: 100.0, timeout_s=2.0)
    assert client.access_token().access_token == "new"
    assert client.access_token().access_token == "new"
    assert len(calls) == 1
    assert store.value["refresh_token"] == "r2"


def test_expiry_and_invalid_grant_clear_credentials_with_typed_redacted_errors() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore({"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_at": 100.0, "scope": list(APPROVED_SPOTIFY_SCOPES)})
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: _Response(400, {"error": "invalid_grant", "error_description": "secret-refresh"}), clock=lambda: 200.0)
    result = client.access_token()
    assert result.code is OAuthErrorCode.INVALID_GRANT
    assert store.deleted
    assert "secret" not in result.message


def test_unauthorized_api_response_cleans_up_and_revoke_is_local_only() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore({"access_token": "access", "refresh_token": "refresh", "expires_at": 9999.0, "scope": list(APPROVED_SPOTIFY_SCOPES)})
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: _Response(401, {}), clock=lambda: 100.0)
    result = client.request("GET", "https://api.spotify.com/v1/me/player")
    assert result.code is OAuthErrorCode.UNAUTHORIZED
    assert store.deleted
    assert client.revoke().code is OAuthErrorCode.OK


def test_disabled_and_transport_failures_are_bounded_typed_errors() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore()
    disabled = OAuthClient(enabled=False, client_id="client", store=store, transport=lambda *args: pytest.fail("transport called"))
    assert disabled.access_token().code is OAuthErrorCode.DISABLED
    store.value = {"access_token": "old", "refresh_token": "refresh", "expires_at": 100.0, "scope": list(APPROVED_SPOTIFY_SCOPES)}
    timeout = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: (_ for _ in ()).throw(TimeoutError("token secret")), clock=lambda: 200.0)
    result = timeout.access_token()
    assert result.code is OAuthErrorCode.NETWORK_TIMEOUT
    assert "secret" not in result.message


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.payload = payload

    def json(self):
        return self.payload


class _MemoryTokenStore:
    def __init__(self, value=None):
        self.value = value
        self.deleted = False

    def load(self):
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        if self.value is None:
            return CredentialResult(CredentialStatus.MISSING)
        return CredentialResult(CredentialStatus.OK, __import__("json").dumps(self.value))

    def save(self, value):
        import json
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        self.value = json.loads(value)
        return CredentialResult(CredentialStatus.OK)

    def delete(self):
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        self.deleted = True
        self.value = None
        return CredentialResult(CredentialStatus.OK)
