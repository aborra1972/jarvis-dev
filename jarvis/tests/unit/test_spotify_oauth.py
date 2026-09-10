import base64
import hashlib

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
