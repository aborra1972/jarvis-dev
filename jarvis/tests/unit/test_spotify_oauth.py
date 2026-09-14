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


def test_client_id_save_ignores_delete_of_absent_disabled_marker() -> None:
    values: dict[tuple[str, str], str] = {}

    class Backend:
        def get_password(self, service, username):
            return values.get((service, username))

        def set_password(self, service, username, value):
            values[(service, username)] = value

        def delete_password(self, service, username):
            if (service, username) not in values:
                raise KeyError(username)
            del values[(service, username)]

    store = KeyringClientIdStore(backend=Backend())
    client_id = "f" * 32
    assert store.save(client_id).status is ClientIdStatus.OK
    loaded = store.load()
    assert loaded.status is ClientIdStatus.OK
    assert loaded.value == client_id


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


def test_authorization_url_requires_explicit_pending_bootstrap() -> None:
    from jarvis.services.spotify import create_spotify_authorization

    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    configuration = {"enabled": True, "authorized": False, "client_id": "a" * 32}
    assert create_spotify_authorization(configuration, transaction=tx) is None
    assert create_spotify_authorization(
        configuration, transaction=tx, allow_pending_authorization=True,
    ) is not None


def test_oauth_factory_requires_explicit_initial_exchange_bootstrap() -> None:
    from jarvis.services.spotify import create_spotify_oauth_client

    configuration = {"enabled": True, "authorized": False, "client_id": "a" * 32}
    assert create_spotify_oauth_client(
        configuration, store=_MemoryTokenStore(), transport=lambda *args: None,
    ) is None
    assert create_spotify_oauth_client(
        configuration, store=_MemoryTokenStore(), transport=lambda *args: None,
        allow_initial_exchange=True,
    ) is not None


def test_initial_exchange_requires_validated_callback() -> None:
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode, authorize_spotify_callback

    calls = []
    store = _MemoryTokenStore()
    client = OAuthClient(
        enabled=True, client_id="a" * 32, store=store,
        transport=lambda *args: calls.append(args) or _Response(
            200, {"access_token": "access", "refresh_token": "refresh",
                  "expires_in": 3600,
                  "scope": "user-read-playback-state user-modify-playback-state"}),
        clock=lambda: 100.0,
    )
    invalid = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    assert authorize_spotify_callback(
        client, invalid,
        "http://127.0.0.1:8888/callback?code=code&state=wrong",
        session_id="session-1", now=101.0,
    ).code is OAuthErrorCode.INVALID_RESPONSE
    assert calls == []
    valid = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    assert authorize_spotify_callback(
        client, valid,
        "http://127.0.0.1:8888/callback?code=code&state=state",
        session_id="session-1", now=101.0,
    ).code is OAuthErrorCode.OK


def test_oauth_factory_fails_closed_without_complete_setup_gate() -> None:
    from jarvis.services.spotify import create_spotify_oauth_client

    def forbidden_transport(*args):
        pytest.fail("OAuth transport must not be initialized")

    assert create_spotify_oauth_client(
        {"enabled": False, "authorized": True, "client_id": "a" * 32},
        store=_MemoryTokenStore(), transport=forbidden_transport,
    ) is None
    assert create_spotify_oauth_client(
        {"enabled": True, "authorized": False, "client_id": "a" * 32},
        store=_MemoryTokenStore(), transport=forbidden_transport,
    ) is None
    assert create_spotify_oauth_client(
        {"enabled": True, "authorized": True, "client_id": None},
        store=_MemoryTokenStore(), transport=forbidden_transport,
    ) is None


def test_oauth_factory_accepts_only_keyring_validated_client_id_and_redacts_setup_state() -> None:
    from jarvis.services.spotify import create_spotify_oauth_client

    client = create_spotify_oauth_client(
        {"enabled": True, "authorized": True, "client_id": "b" * 32},
        store=_MemoryTokenStore(), transport=lambda *args: pytest.fail("transport called"),
    )
    assert client is not None
    assert "b" * 32 not in repr(client)


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


def test_live_authorization_binds_loopback_opens_injected_browser_and_saves_tokens():
    from jarvis.services.spotify import OAuthErrorCode, run_spotify_live_authorization

    events = []
    tx_holder = {}

    class Server:
        def serve_once(self):
            tx = tx_holder["transaction"]
            return f"http://127.0.0.1:8888/callback?code=auth-code&state={tx.state}"
        def shutdown(self):
            events.append("shutdown")

    def server_factory(host, port, callback, timeout):
        events.append(("server", host, port, callback, timeout))
        return Server()

    store = _MemoryTokenStore()
    result = run_spotify_live_authorization(
        {"enabled": True, "authorized": False, "client_id": "a" * 32},
        browser_opener=lambda url: events.append(("browser", url)),
        server_factory=server_factory,
        transport=lambda *args: _Response(200, {
            "access_token": "access", "refresh_token": "refresh", "expires_in": 3600,
            "scope": "user-read-playback-state user-modify-playback-state",
        }),
        clock=lambda: 100.0, store=store,
        transaction_factory=lambda session_id, now, ttl_s: tx_holder.setdefault(
            "transaction", create_pkce_transaction(session_id, now=now, ttl_s=ttl_s,
                                                    token_factory=lambda: "state")),
    )
    assert result.code is OAuthErrorCode.OK
    assert events[0][0] == "server"
    assert events[1][0] == "browser"
    assert events[-1] == "shutdown"
    assert store.value["access_token"] == "access"


def test_live_authorization_allows_bounded_120_second_callback_window():
    from jarvis.services.spotify import OAuthErrorCode, run_spotify_live_authorization

    seen = {}
    tx_holder = {}

    class Server:
        def serve_once(self):
            tx = tx_holder["transaction"]
            return f"http://127.0.0.1:8888/callback?code=c&state={tx.state}"
        def shutdown(self):
            seen["closed"] = True

    def server_factory(host, port, callback, timeout):
        seen["server"] = (host, port, timeout)
        return Server()

    result = run_spotify_live_authorization(
        {"enabled": True, "authorized": False, "client_id": "a" * 32},
        browser_opener=lambda url: None, server_factory=server_factory,
        transport=lambda *args: _Response(200, {
            "access_token": "access", "refresh_token": "refresh", "expires_in": 3600,
            "scope": "user-read-playback-state user-modify-playback-state",
        }),
        clock=lambda: 100.0, store=_MemoryTokenStore(), timeout_s=120.0,
        transaction_factory=lambda session_id, now, ttl_s: tx_holder.setdefault(
            "transaction", create_pkce_transaction(session_id, now=now, ttl_s=ttl_s,
                                                    token_factory=lambda: "state")),
    )
    assert result.code is OAuthErrorCode.OK
    assert seen["server"] == ("127.0.0.1", 8888, 120.0)
    assert seen["closed"]


def test_live_authorization_rejects_timeout_above_hard_max():
    from jarvis.services.spotify import OAuthErrorCode, run_spotify_live_authorization

    opened = []
    result = run_spotify_live_authorization(
        {"enabled": True, "authorized": True, "client_id": "a" * 32},
        browser_opener=opened.append,
        server_factory=lambda *args: pytest.fail("server must not be created"),
        transport=lambda *args: pytest.fail("transport must not be called"),
        store=_MemoryTokenStore(), timeout_s=120.1,
    )
    assert result.code is OAuthErrorCode.PROVIDER_ERROR
    assert opened == []


def test_live_authorization_fails_closed_on_bind_error_and_does_not_open_browser():
    from jarvis.services.spotify import OAuthErrorCode, run_spotify_live_authorization

    opened = []
    def broken_server(*args):
        raise OSError("port unavailable")

    result = run_spotify_live_authorization(
        {"enabled": True, "authorized": True, "client_id": "a" * 32},
        browser_opener=opened.append, server_factory=broken_server,
        transport=lambda *args: pytest.fail("transport called"), clock=lambda: 100.0,
        store=_MemoryTokenStore(),
    )
    assert result.code is OAuthErrorCode.PROVIDER_ERROR
    assert opened == []


def test_live_authorization_rejects_invalid_or_declined_callback_without_transport():
    from jarvis.services.spotify import OAuthErrorCode, run_spotify_live_authorization

    for callback_url, expected in (
        ("http://127.0.0.1:8888/callback?code=c&state=wrong", OAuthErrorCode.INVALID_RESPONSE),
        ("http://127.0.0.1:8888/callback?error=access_denied", OAuthErrorCode.NOT_AUTHORIZED),
    ):
        calls = []
        def server_factory(host, port, callback, timeout, value=callback_url):
            class Server:
                def serve_once(self):
                    return value
                def shutdown(self):
                    pass
            return Server()
        result = run_spotify_live_authorization(
            {"enabled": True, "authorized": True, "client_id": "a" * 32},
            browser_opener=lambda url: None, server_factory=server_factory,
            transport=lambda *args: calls.append(args), clock=lambda: 100.0,
            store=_MemoryTokenStore(),
        )
        assert result.code is expected
        assert calls == []


def test_authorization_url_uses_exact_redirect_and_scopes_without_repr_leaks():

    from jarvis.services.spotify import create_spotify_authorization, redacted_authorization_url

    tx = create_pkce_transaction("session-1", now=100.0, token_factory=iter(["v" * 43, "state-secret"]).__next__)
    url = create_spotify_authorization(
        {"enabled": True, "authorized": True, "client_id": "a" * 32}, transaction=tx,
    )
    assert "redirect_uri=http%3A%2F%2F127.0.0.1%3A8888%2Fcallback" in url
    assert "scope=user-modify-playback-state+user-read-playback-state" in url
    assert "state-secret" in url
    redacted = redacted_authorization_url(url)
    assert "state-secret" not in redacted
    assert tx.verifier not in redacted
    assert "%5Bredacted%5D" in redacted


def test_callback_validation_failure_preserves_error_code_and_exposes_safe_category():
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode, authorize_spotify_callback

    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state-secret")
    client = OAuthClient(
        enabled=True, client_id="a" * 32, store=_MemoryTokenStore(),
        transport=lambda *args: pytest.fail("invalid callback must not use transport"),
        clock=lambda: 100.0,
    )
    result = authorize_spotify_callback(
        client, tx,
        "http://127.0.0.1:8888/callback?code=code-secret&state=wrong-state",
        session_id="session-1", now=101.0,
    )

    assert result.code is OAuthErrorCode.INVALID_RESPONSE
    assert result.callback_code is OAuthCallbackCode.STATE_MISMATCH
    assert result.message == OAuthCallbackCode.STATE_MISMATCH.value
    assert all(secret not in result.message for secret in (
        "http://127.0.0.1:8888/callback", "code-secret", "wrong-state", "state-secret",
    ))


def test_injected_authorization_callback_exchange_success_and_failures():
    from jarvis.services.spotify import OAuthClient, OAuthErrorCode, authorize_spotify_callback

    tx = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    store = _MemoryTokenStore()
    calls = []
    client = OAuthClient(
        enabled=True, client_id="a" * 32, store=store,
        transport=lambda *args: calls.append(args) or _Response(
            200, {"access_token": "access-secret", "refresh_token": "refresh-secret",
                  "expires_in": 3600, "scope": "user-read-playback-state user-modify-playback-state"}),
        clock=lambda: 100.0,
    )
    result = authorize_spotify_callback(
        client, tx, "http://127.0.0.1:8888/callback?code=code-secret&state=state",
        session_id="session-1", now=101.0,
    )
    assert result.ok and len(calls) == 1
    assert "code-secret" not in result.message and "access-secret" not in repr(result)

    bad = create_pkce_transaction("session-1", now=100.0, token_factory=lambda: "state")
    failed = authorize_spotify_callback(
        client, bad, "http://127.0.0.1:8888/callback?code=code&state=wrong",
        session_id="session-1", now=101.0,
    )
    assert failed.code is OAuthErrorCode.INVALID_RESPONSE
    assert len(calls) == 1
