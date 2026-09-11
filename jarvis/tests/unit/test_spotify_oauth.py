import base64
import hashlib

import pytest

from jarvis import cli
from jarvis.services.spotify import (
    APPROVED_SPOTIFY_SCOPES,
    ClientIdStatus,
    CredentialStatus,
    KeyringClientIdStore,
    KeyringCredentialStore,
    resolve_spotify_client_id,
    OAuthCallbackCode,
    create_pkce_transaction,
    parse_pkce_callback,
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


def test_callback_accepts_exact_loopback_shape_and_consumes_transaction() -> None:
    tx = create_pkce_transaction("session-1", now=100.0, ttl_s=60.0,
                                 token_factory=iter(["v" * 43, "state"]).__next__)
    result = parse_pkce_callback(
        "http://127.0.0.1:8888/callback?code=auth-code&state=state",
        transaction=tx, session_id="session-1", now=101.0,
    )
    assert result.code is OAuthCallbackCode.OK
    assert result.authorization_code == "auth-code"
    assert not tx.valid_for("session-1", now=101.0)


def test_callback_rejects_wrong_redirect_shape_and_query_content() -> None:
    callbacks = (
        "http://127.0.0.1:8888/not-callback?code=c&state=s",
        "http://127.0.0.1:8889/callback?code=c&state=s",
        "https://127.0.0.1:8888/callback?code=c&state=s",
        "http://127.0.0.1:8888/callback?code=c&state=s&extra=x",
        "http://127.0.0.1:8888/callback#code=c&state=s",
    )
    for callback in callbacks:
        tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "s")
        result = parse_pkce_callback(callback, transaction=tx, session_id="session-1", now=101.0)
        assert result.code is OAuthCallbackCode.INVALID_CALLBACK
        assert tx.valid_for("session-1", now=101.0)


def test_callback_rejects_state_session_and_expiry_without_consuming() -> None:
    cases = (("wrong-state", "session-1", 101.0, OAuthCallbackCode.STATE_MISMATCH),
             ("state", "other-session", 101.0, OAuthCallbackCode.SESSION_MISMATCH),
             ("state", "session-1", 160.0, OAuthCallbackCode.EXPIRED))
    for state, session, now, expected in cases:
        tx = create_pkce_transaction("session-1", now=100.0, ttl_s=60.0,
                                     token_factory=iter(["v", "state"]).__next__)
        result = parse_pkce_callback(
            f"http://127.0.0.1:8888/callback?code=c&state={state}",
            transaction=tx, session_id=session, now=now,
        )
        assert result.code is expected
        assert tx.valid_for("session-1", now=101.0)


def test_callback_is_one_time_and_requires_code() -> None:
    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    callback = "http://127.0.0.1:8888/callback?code=c&state=state"
    assert parse_pkce_callback(callback, transaction=tx, session_id="session-1", now=101.0).code is OAuthCallbackCode.OK
    assert parse_pkce_callback(callback, transaction=tx, session_id="session-1", now=102.0).code is OAuthCallbackCode.ALREADY_CONSUMED
    fresh = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    assert parse_pkce_callback("http://127.0.0.1:8888/callback?state=state", transaction=fresh,
                               session_id="session-1", now=101.0).code is OAuthCallbackCode.INVALID_CALLBACK


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


def test_keyring_disable_keeps_durable_marker_after_token_deletion() -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))

        def set_password(self, service, username, value):
            values[(service, username)] = value

        def delete_password(self, service, username):
            values.pop((service, username), None)

    store = KeyringCredentialStore(backend=Backend())
    assert store.save("token").status is CredentialStatus.OK
    assert store.disable().status is CredentialStatus.OK
    assert values == {("jarvis.spotify", "oauth:disabled"): "1"}
    assert KeyringCredentialStore(backend=store._backend).load().status is CredentialStatus.DISABLED


def test_client_id_store_is_separate_validated_and_redacted() -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))

        def set_password(self, service, username, value):
            values[(service, username)] = value

        def delete_password(self, service, username):
            values.pop((service, username), None)

    store = KeyringClientIdStore(backend=Backend())
    client_id = "a" * 32
    assert store.save(client_id).status is ClientIdStatus.OK
    loaded = store.load()
    assert loaded.status is ClientIdStatus.OK
    assert loaded.value == client_id
    assert client_id not in repr(loaded)
    assert values == {("jarvis.spotify.client", "client_id"): client_id}
    assert store.save("not-a-client-id").status is ClientIdStatus.INVALID
    assert store.delete().status is ClientIdStatus.OK
    assert store.load().status is ClientIdStatus.MISSING


def test_client_id_store_disable_is_durable_and_storage_failures_are_typed() -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))

        def set_password(self, service, username, value):
            values[(service, username)] = value

        def delete_password(self, service, username):
            values.pop((service, username), None)

    store = KeyringClientIdStore(backend=Backend())
    assert store.save("b" * 32).status is ClientIdStatus.OK
    assert store.disable().status is ClientIdStatus.OK
    assert store.load().status is ClientIdStatus.DISABLED
    assert store.enable().status is ClientIdStatus.OK
    assert store.load().status is ClientIdStatus.MISSING

    class Broken:
        def get_password(self, service, username):
            raise RuntimeError
        def set_password(self, service, username, value):
            raise RuntimeError
        def delete_password(self, service, username):
            raise RuntimeError

    broken = KeyringClientIdStore(backend=Broken())
    assert broken.load().status is ClientIdStatus.STORAGE_UNAVAILABLE
    assert broken.save("c" * 32).status is ClientIdStatus.STORAGE_UNAVAILABLE


def test_client_id_resolver_prefers_valid_explicit_setup_value() -> None:
    store = KeyringClientIdStore(backend=object())
    explicit = "d" * 32
    result = resolve_spotify_client_id(explicit, store=store)
    assert result.status is ClientIdStatus.OK
    assert result.value == explicit
    assert explicit not in repr(result)


def test_client_id_resolver_recovers_stored_value_without_explicit_config() -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))
        def set_password(self, service, username, value):
            values[(service, username)] = value
        def delete_password(self, service, username):
            values.pop((service, username), None)

    store = KeyringClientIdStore(backend=Backend())
    store.save("e" * 32)
    result = resolve_spotify_client_id(None, store=store)
    assert result.status is ClientIdStatus.OK
    assert result.value == "e" * 32


def test_spotify_setup_saves_hidden_client_id_without_secret(monkeypatch, capsys) -> None:
    values = {}

    class Store:
        def save(self, value):
            values["client_id"] = value
            return type("Result", (), {"status": ClientIdStatus.OK})()

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "getpass", type("Getpass", (), {"getpass": lambda *args: "c" * 32}))
    monkeypatch.setattr(cli, "KeyringClientIdStore", lambda: Store())
    assert cli.main(["setup", "spotify"]) == 0
    assert values == {"client_id": "c" * 32}
    assert "c" * 32 not in capsys.readouterr().out


def test_spotify_setup_rejects_invalid_client_id_without_writing(monkeypatch, capsys) -> None:
    saved = []

    class Store:
        def save(self, value):
            saved.append(value)
            return type("Result", (), {"status": ClientIdStatus.INVALID})()

    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "getpass", type("Getpass", (), {"getpass": lambda *args: "not-valid"}))
    monkeypatch.setattr(cli, "KeyringClientIdStore", lambda: Store())
    assert cli.main(["spotify", "setup"]) == 1
    assert saved == []
    assert "not-valid" not in capsys.readouterr().err


def test_spotify_setup_noninteractive_fails_without_writing(monkeypatch, capsys) -> None:
    saved = []
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli, "KeyringClientIdStore", lambda: type("Store", (), {
        "save": lambda self, value: saved.append(value),
    })())
    assert cli.main(["setup", "spotify"]) == 1
    assert saved == []
    assert "interactivo" in capsys.readouterr().err.lower()


def test_missing_keyring_import_is_typed_storage_unavailable(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def missing_keyring(name, *args, **kwargs):
        if name == "keyring":
            raise ModuleNotFoundError("No module named keyring")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_keyring)
    assert KeyringCredentialStore().load().status is CredentialStatus.STORAGE_UNAVAILABLE
    assert KeyringClientIdStore().load().status is ClientIdStatus.STORAGE_UNAVAILABLE


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


@pytest.mark.parametrize("expires_in", ["not-a-number", "nan", "inf", 0, -1, True])
def test_malformed_or_nonpositive_expiry_fails_closed(expires_in) -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore()
    client = OAuthClient(
        enabled=True,
        client_id="client",
        store=store,
        transport=lambda *args: _Response(
            200,
            {"access_token": "access", "refresh_token": "refresh", "expires_in": expires_in},
        ),
        clock=lambda: 100.0,
    )
    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "v" * 43)

    result = client.exchange_code(tx, "code", session_id="session-1")

    assert result.code is OAuthErrorCode.INVALID_RESPONSE
    assert store.value is None


def test_disable_persists_marker_and_blocks_reactivation_until_authorized() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore({"access_token": "old", "refresh_token": "refresh", "expires_at": 9999.0, "scope": list(APPROVED_SPOTIFY_SCOPES)})
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: pytest.fail("transport called"))

    assert client.disable().code is OAuthErrorCode.DISABLED
    assert store.disabled
    store.value = {"access_token": "restored", "refresh_token": "refresh", "expires_at": 9999.0, "scope": list(APPROVED_SPOTIFY_SCOPES)}
    assert client.access_token().code is OAuthErrorCode.DISABLED
    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "v" * 43)
    assert client.exchange_code(tx, "code", session_id="session-1").code is OAuthErrorCode.DISABLED


def test_explicit_enable_clears_durable_disable() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore()
    store.disabled = True
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: pytest.fail("transport called"))

    assert client.enable().code is OAuthErrorCode.OK
    assert not store.disabled


@pytest.mark.parametrize("scope", [None, 42, [["user-read-playback-state"]], ["unexpected"], ["user-read-playback-state", None]])
def test_malformed_persisted_scope_fails_closed_without_raising(scope) -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore({"access_token": "access", "refresh_token": "refresh", "expires_at": 9999.0, "scope": scope})
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: pytest.fail("transport called"))

    assert client.access_token().code is OAuthErrorCode.INVALID_RESPONSE
    assert store.deleted


def test_disabled_marker_is_not_replaced_by_deleted_credentials() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode

    store = _MemoryTokenStore()
    store.disabled = True
    client = OAuthClient(enabled=True, client_id="client", store=store, transport=lambda *args: pytest.fail("transport called"))

    assert client.access_token().code is OAuthErrorCode.DISABLED
    assert store.value is None


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
        self.disabled = False

    def load(self):
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        if self.disabled:
            return CredentialResult(CredentialStatus.DISABLED)
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
        self.disabled = False
        return CredentialResult(CredentialStatus.OK)

    def disable(self):
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        self.disabled = True
        self.value = None
        return CredentialResult(CredentialStatus.OK)

    def enable(self):
        from jarvis.services.spotify import CredentialResult, CredentialStatus
        self.disabled = False
        return CredentialResult(CredentialStatus.OK)
