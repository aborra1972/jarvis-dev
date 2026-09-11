"""Credential-free, Spotify-only local MPRIS control."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import secrets
import subprocess
import threading
import time
from urllib.parse import parse_qs, urlsplit
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult


class SpotifyErrorCode(str, Enum):
    OK = "ok"
    BINARY_MISSING = "binary_missing"
    TIMEOUT = "timeout"
    MPRIS_UNAVAILABLE = "mpris_unavailable"
    IDENTITY_MISSING = "identity_missing"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"
    CONTROL_FAILED = "control_failed"
    STATE_UNKNOWN = "state_unknown"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class SpotifyResult:
    ok: bool
    code: SpotifyErrorCode
    message: str
    state: str | None = None


_SAFE_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


APPROVED_SPOTIFY_SCOPES = frozenset({
    "user-read-playback-state",
    "user-modify-playback-state",
})
LOOPBACK_REDIRECT_URI = "http://127.0.0.1:8888/callback"


class OAuthCallbackCode(str, Enum):
    OK = "ok"
    INVALID_CALLBACK = "invalid_callback"
    STATE_MISMATCH = "state_mismatch"
    SESSION_MISMATCH = "session_mismatch"
    EXPIRED = "expired"
    ALREADY_CONSUMED = "already_consumed"


@dataclass(frozen=True, repr=False)
class OAuthCallbackResult:
    code: OAuthCallbackCode
    authorization_code: str | None = field(default=None, repr=False)


@dataclass
class PKCETransaction:
    """Volatile, session-bound authorization transaction; never persisted."""

    verifier: str = field(repr=False)
    state: str = field(repr=False)
    code_challenge: str
    session_id: str = field(repr=False)
    expires_at: float
    _consumed: bool = field(default=False, repr=False)

    def valid_for(self, session_id: str, *, now: float) -> bool:
        return not self._consumed and session_id == self.session_id and now < self.expires_at

    def consume(self, session_id: str, *, now: float) -> bool:
        if not self.valid_for(session_id, now=now):
            return False
        self._consumed = True
        return True


def parse_pkce_callback(
    callback_url: str,
    *,
    transaction: PKCETransaction,
    session_id: str,
    now: float,
) -> OAuthCallbackResult:
    """Validate one injected loopback callback without performing I/O."""
    if not isinstance(callback_url, str):
        return OAuthCallbackResult(OAuthCallbackCode.INVALID_CALLBACK)
    parsed = urlsplit(callback_url)
    if (parsed.scheme, parsed.netloc, parsed.path) != ("http", "127.0.0.1:8888", "/callback"):
        return OAuthCallbackResult(OAuthCallbackCode.INVALID_CALLBACK)
    if parsed.fragment:
        return OAuthCallbackResult(OAuthCallbackCode.INVALID_CALLBACK)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if set(query) != {"code", "state"} or any(len(values) != 1 or not values[0] for values in query.values()):
        return OAuthCallbackResult(OAuthCallbackCode.INVALID_CALLBACK)
    if transaction._consumed:
        return OAuthCallbackResult(OAuthCallbackCode.ALREADY_CONSUMED)
    if session_id != transaction.session_id:
        return OAuthCallbackResult(OAuthCallbackCode.SESSION_MISMATCH)
    if now >= transaction.expires_at:
        return OAuthCallbackResult(OAuthCallbackCode.EXPIRED)
    if not hmac.compare_digest(query["state"][0], transaction.state):
        return OAuthCallbackResult(OAuthCallbackCode.STATE_MISMATCH)
    if not transaction.consume(session_id, now=now):
        return OAuthCallbackResult(OAuthCallbackCode.EXPIRED)
    return OAuthCallbackResult(OAuthCallbackCode.OK, query["code"][0])


def create_pkce_transaction(
    session_id: str,
    *,
    now: float,
    ttl_s: float = 300.0,
    token_factory: Callable[[], str] | None = None,
) -> PKCETransaction:
    """Create PKCE material with exact S256 and a short, bounded lifetime."""
    if not session_id or not 1.0 <= ttl_s <= 600.0:
        raise ValueError("invalid PKCE transaction")
    make_token = token_factory or (lambda: secrets.token_urlsafe(32))
    verifier = make_token()
    state = make_token()
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PKCETransaction(verifier, state, challenge, session_id, now + ttl_s)


class CredentialStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    DISABLED = "disabled"
    STORAGE_UNAVAILABLE = "storage_unavailable"


@dataclass(frozen=True, repr=False)
class CredentialResult:
    status: CredentialStatus
    value: str | None = field(default=None, repr=False)


class ClientIdStatus(str, Enum):
    OK = "ok"
    MISSING = "missing"
    INVALID = "invalid"
    DISABLED = "disabled"
    STORAGE_UNAVAILABLE = "storage_unavailable"


@dataclass(frozen=True, repr=False)
class ClientIdResult:
    status: ClientIdStatus
    value: str | None = field(default=None, repr=False)


_SPOTIFY_CLIENT_ID = re.compile(r"[A-Za-z0-9]{32}\Z")


class KeyringClientIdStore:
    """Keyring-only store kept separate from OAuth tokens."""

    SERVICE = "jarvis.spotify.client"
    USERNAME = "client_id"

    def __init__(self, *, backend: Any | None = None) -> None:
        self._backend = backend if backend is not None else KeyringCredentialStore._default_backend()
        self._disabled_username = f"{self.USERNAME}:disabled"

    @staticmethod
    def _valid(value: Any) -> bool:
        return isinstance(value, str) and _SPOTIFY_CLIENT_ID.fullmatch(value) is not None

    def load(self) -> ClientIdResult:
        if self._backend is None:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        try:
            if self._backend.get_password(self.SERVICE, self._disabled_username) == "1":
                return ClientIdResult(ClientIdStatus.DISABLED)
            value = self._backend.get_password(self.SERVICE, self.USERNAME)
        except Exception:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        if value is None:
            return ClientIdResult(ClientIdStatus.MISSING)
        return ClientIdResult(ClientIdStatus.OK, value) if self._valid(value) else ClientIdResult(ClientIdStatus.INVALID)

    def save(self, value: str) -> ClientIdResult:
        if not self._valid(value):
            return ClientIdResult(ClientIdStatus.INVALID)
        if self._backend is None:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.set_password(self.SERVICE, self.USERNAME, value)
            self._backend.delete_password(self.SERVICE, self._disabled_username)
        except Exception:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        return ClientIdResult(ClientIdStatus.OK)

    def disable(self) -> ClientIdResult:
        if self._backend is None:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.set_password(self.SERVICE, self._disabled_username, "1")
            self._backend.delete_password(self.SERVICE, self.USERNAME)
        except Exception:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        return ClientIdResult(ClientIdStatus.OK)

    def enable(self) -> ClientIdResult:
        if self._backend is None:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.delete_password(self.SERVICE, self._disabled_username)
        except Exception:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        return ClientIdResult(ClientIdStatus.OK)

    def delete(self) -> ClientIdResult:
        if self._backend is None:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.delete_password(self.SERVICE, self.USERNAME)
        except Exception:
            return ClientIdResult(ClientIdStatus.STORAGE_UNAVAILABLE)
        return ClientIdResult(ClientIdStatus.OK)


def resolve_spotify_client_id(
    configured: str | None = None, *, store: KeyringClientIdStore | None = None,
) -> ClientIdResult:
    """Use an explicit setup value, otherwise recover the keyring value."""
    if configured is not None:
        return (ClientIdResult(ClientIdStatus.OK, configured)
                if KeyringClientIdStore._valid(configured)
                else ClientIdResult(ClientIdStatus.INVALID))
    return (store or KeyringClientIdStore()).load()


SpotifyClientIdStore = KeyringClientIdStore


class KeyringCredentialStore:
    """Keyring-only credential boundary; unavailable storage fails closed."""

    def __init__(self, *, backend: Any | None = None, service: str = "jarvis.spotify", username: str = "oauth") -> None:
        self._backend = backend if backend is not None else self._default_backend()
        self._service = service
        self._username = username
        self._disabled_username = f"{username}:disabled"

    @staticmethod
    def _default_backend() -> Any | None:
        try:
            import keyring
            return keyring
        except (ImportError, RuntimeError):
            return None

    def load(self) -> CredentialResult:
        if self._backend is None:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        try:
            if self._backend.get_password(self._service, self._disabled_username) == "1":
                return CredentialResult(CredentialStatus.DISABLED)
            value = self._backend.get_password(self._service, self._username)
        except Exception:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        return CredentialResult(CredentialStatus.OK, value) if value is not None else CredentialResult(CredentialStatus.MISSING)

    def save(self, value: str) -> CredentialResult:
        if self._backend is None:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.set_password(self._service, self._username, value)
            self._backend.delete_password(self._service, self._disabled_username)
        except Exception:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        return CredentialResult(CredentialStatus.OK)

    def enable(self) -> CredentialResult:
        if self._backend is None:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.delete_password(self._service, self._disabled_username)
        except Exception:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        return CredentialResult(CredentialStatus.OK)

    def disable(self) -> CredentialResult:
        if self._backend is None:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.set_password(self._service, self._disabled_username, "1")
            self._backend.delete_password(self._service, self._username)
        except Exception:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        return CredentialResult(CredentialStatus.OK)

    def delete(self) -> CredentialResult:
        if self._backend is None:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        try:
            self._backend.delete_password(self._service, self._username)
        except Exception:
            return CredentialResult(CredentialStatus.STORAGE_UNAVAILABLE)
        return CredentialResult(CredentialStatus.OK)


class OAuthErrorCode(str, Enum):
    OK = "ok"
    DISABLED = "disabled"
    NOT_AUTHORIZED = "not_authorized"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    NETWORK_TIMEOUT = "network_timeout"
    PROVIDER_ERROR = "provider_error"
    INVALID_GRANT = "invalid_grant"
    UNAUTHORIZED = "unauthorized"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True, repr=False)
class OAuthResult:
    code: OAuthErrorCode
    message: str
    access_token: str | None = field(default=None, repr=False)
    payload: object | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.code is OAuthErrorCode.OK


class OAuthClient:
    """Offline-testable Spotify token lifecycle with a bounded transport seam."""

    TOKEN_URL = "https://accounts.spotify.com/api/token"
    _EXPIRY_LEEWAY_S = 60.0

    def __init__(self, *, enabled: bool, client_id: str | None, store: Any,
                 transport: Callable[..., Any], clock: Callable[[], float] = time.time,
                 timeout_s: float = 5.0) -> None:
        if not 0.1 <= timeout_s <= 30.0:
            raise ValueError("invalid OAuth timeout")
        self._enabled = bool(enabled)
        self._client_id = client_id
        self._store = store
        self._transport = transport
        self._clock = clock
        self._timeout = float(timeout_s)
        self._refresh_lock = threading.Lock()

    def exchange_code(self, transaction: PKCETransaction, code: str, *, session_id: str) -> OAuthResult:
        if not self._enabled:
            return self._result(OAuthErrorCode.DISABLED)
        stored = self._store.load()
        if stored.status is CredentialStatus.DISABLED:
            return self._result(OAuthErrorCode.DISABLED)
        if stored.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        if not code or not transaction.consume(session_id, now=self._clock()):
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        response = self._send({
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": LOOPBACK_REDIRECT_URI,
            "client_id": self._client_id or "", "code_verifier": transaction.verifier,
            "scope": " ".join(sorted(APPROVED_SPOTIFY_SCOPES)),
        })
        result = self._process_token_response(response)
        if result.ok:
            return self._save_token(result)
        return result

    def access_token(self) -> OAuthResult:
        if not self._enabled:
            return self._result(OAuthErrorCode.DISABLED)
        loaded = self._load_token()
        if not loaded.ok:
            return loaded
        record = loaded.payload
        if self._valid_record(record) and record["expires_at"] - self._clock() > self._EXPIRY_LEEWAY_S:
            return OAuthResult(OAuthErrorCode.OK, "", access_token=record["access_token"])
        with self._refresh_lock:
            # Another caller may have completed rotation while this caller waited.
            loaded = self._load_token()
            if not loaded.ok:
                return loaded
            record = loaded.payload
            if self._valid_record(record) and record["expires_at"] - self._clock() > self._EXPIRY_LEEWAY_S:
                return OAuthResult(OAuthErrorCode.OK, "", access_token=record["access_token"])
            refresh_token = record.get("refresh_token") if isinstance(record, dict) else None
            if not refresh_token:
                return self._cleanup(OAuthErrorCode.NOT_AUTHORIZED)
            result = self._process_token_response(self._send({
                "grant_type": "refresh_token", "refresh_token": refresh_token,
                "client_id": self._client_id or "",
                "scope": " ".join(sorted(APPROVED_SPOTIFY_SCOPES)),
            }), old_refresh_token=refresh_token)
            return self._save_token(result) if result.ok else result

    def request(self, method: str, url: str, data: dict[str, str] | None = None) -> OAuthResult:
        token = self.access_token()
        if not token.ok:
            return token
        try:
            response = self._transport(method, url, data or {},
                                       {"Authorization": f"Bearer {token.access_token}"}, self._timeout)
        except (TimeoutError, OSError):
            return self._result(OAuthErrorCode.NETWORK_TIMEOUT)
        except Exception:
            return self._result(OAuthErrorCode.PROVIDER_ERROR)
        status = getattr(response, "status_code", None)
        if status == 401:
            return self._cleanup(OAuthErrorCode.UNAUTHORIZED)
        if not isinstance(status, int) or status < 200 or status >= 300:
            return self._result(OAuthErrorCode.PROVIDER_ERROR)
        return OAuthResult(OAuthErrorCode.OK, "", payload=None)

    def revoke(self) -> OAuthResult:
        return self._cleanup(OAuthErrorCode.OK)

    def enable(self) -> OAuthResult:
        enable = getattr(self._store, "enable", None)
        if not callable(enable):
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        result = enable()
        if result.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        return self._result(OAuthErrorCode.OK)

    def disable(self) -> OAuthResult:
        disable = getattr(self._store, "disable", None)
        if not callable(disable):
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        result = disable()
        if result.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        return self._result(OAuthErrorCode.DISABLED)

    def _send(self, data: dict[str, str]) -> Any:
        try:
            return self._transport("POST", self.TOKEN_URL, data,
                                   {"Content-Type": "application/x-www-form-urlencoded"}, self._timeout)
        except (TimeoutError, OSError):
            return _OAuthTransportFailure(OAuthErrorCode.NETWORK_TIMEOUT)
        except Exception:
            return _OAuthTransportFailure(OAuthErrorCode.PROVIDER_ERROR)

    def _process_token_response(self, response: Any, *, old_refresh_token: str | None = None) -> OAuthResult:
        if isinstance(response, _OAuthTransportFailure):
            return self._result(response.code)
        status = getattr(response, "status_code", None)
        try:
            payload = response.json()
        except Exception:
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        if status in {400, 401} and isinstance(payload, dict) and payload.get("error") == "invalid_grant":
            return self._cleanup(OAuthErrorCode.INVALID_GRANT)
        if status != 200 or not isinstance(payload, dict):
            return self._result(OAuthErrorCode.PROVIDER_ERROR)
        access = payload.get("access_token")
        expires = payload.get("expires_in")
        refresh = payload.get("refresh_token") or old_refresh_token
        if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        if isinstance(expires, bool):
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        try:
            expiry_seconds = float(expires)
        except (TypeError, ValueError):
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        if not math.isfinite(expiry_seconds) or expiry_seconds <= 0:
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        expires_at = self._clock() + expiry_seconds
        scopes = set(str(payload.get("scope", "")).split()) or set(APPROVED_SPOTIFY_SCOPES)
        if scopes != APPROVED_SPOTIFY_SCOPES:
            return self._result(OAuthErrorCode.INVALID_RESPONSE)
        return OAuthResult(OAuthErrorCode.OK, "", access_token=access,
                           payload={"access_token": access, "refresh_token": refresh,
                                    "expires_at": expires_at, "scope": sorted(scopes)})

    def _load_token(self) -> OAuthResult:
        result = self._store.load()
        if result.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        if result.status is CredentialStatus.DISABLED:
            return self._result(OAuthErrorCode.DISABLED)
        if result.status is CredentialStatus.MISSING or not result.value:
            return self._result(OAuthErrorCode.NOT_AUTHORIZED)
        try:
            record = json.loads(result.value)
        except (TypeError, ValueError):
            return self._cleanup(OAuthErrorCode.INVALID_RESPONSE)
        if isinstance(record, dict) and record.get("disabled") is True:
            return self._result(OAuthErrorCode.DISABLED)
        return OAuthResult(OAuthErrorCode.OK, "", payload=record) if self._valid_record(record) else self._cleanup(OAuthErrorCode.INVALID_RESPONSE)

    @staticmethod
    def _valid_record(record: Any) -> bool:
        if not (isinstance(record, dict) and isinstance(record.get("access_token"), str)
                and isinstance(record.get("refresh_token"), str)
                and isinstance(record.get("expires_at"), (int, float))
                and not isinstance(record.get("expires_at"), bool)
                and math.isfinite(record["expires_at"]) and record["expires_at"] > 0):
            return False
        scope = record.get("scope")
        return (isinstance(scope, (list, tuple, set, frozenset))
                and all(isinstance(member, str) for member in scope)
                and set(scope) == APPROVED_SPOTIFY_SCOPES)

    def _save_token(self, result: OAuthResult) -> OAuthResult:
        saved = self._store.save(json.dumps(result.payload, separators=(",", ":")))
        if saved.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        return OAuthResult(OAuthErrorCode.OK, "", access_token=result.access_token)

    def _cleanup(self, code: OAuthErrorCode) -> OAuthResult:
        deleted = self._store.delete()
        if deleted.status is CredentialStatus.STORAGE_UNAVAILABLE:
            return self._result(OAuthErrorCode.STORAGE_UNAVAILABLE)
        return self._result(code)

    @staticmethod
    def _result(code: OAuthErrorCode) -> OAuthResult:
        messages = {
            OAuthErrorCode.DISABLED: "Spotify está deshabilitado.",
            OAuthErrorCode.NOT_AUTHORIZED: "Spotify requiere autorización.",
            OAuthErrorCode.STORAGE_UNAVAILABLE: "El almacenamiento seguro no está disponible.",
            OAuthErrorCode.NETWORK_TIMEOUT: "Spotify tardó demasiado en responder.",
            OAuthErrorCode.INVALID_GRANT: "La autorización de Spotify venció; debe autorizarse nuevamente.",
            OAuthErrorCode.UNAUTHORIZED: "La autorización de Spotify ya no es válida.",
        }
        return OAuthResult(code, messages.get(code, "No pude completar la autorización de Spotify."))


@dataclass(frozen=True)
class _OAuthTransportFailure:
    code: OAuthErrorCode


# Descriptive alias for callers that prefer the provider-specific name.
SpotifyOAuthClient = OAuthClient


class LocalSpotifyAdapter:
    """Run only fixed playerctl operations against one configured Spotify identity."""

    def __init__(
        self,
        *,
        runner: Callable[..., Any] | None = None,
        playerctl_bin: str = "playerctl",
        identity: str = "spotify",
        timeout_s: float = 2.0,
        operation: Any | None = None,
    ) -> None:
        if not _SAFE_IDENTITY.fullmatch(identity):
            raise ValueError("invalid Spotify identity")
        if not isinstance(timeout_s, (int, float)) or not 0 < timeout_s <= 30:
            raise ValueError("invalid Spotify timeout")
        self._runner = runner
        self._bin = playerctl_bin
        self._identity = identity
        self._timeout = float(timeout_s)
        self._operation = operation

    def play(self) -> SpotifyResult:
        return self._control("play", "Playing")

    def pause(self) -> SpotifyResult:
        return self._control("pause", "Paused")

    def _control(self, action: str, expected: str) -> SpotifyResult:
        if self._cancelled():
            return self._cancelled_result()
        probe = self._run([self._bin, "-l"])
        if self._cancelled():
            return self._cancelled_result()
        if isinstance(probe, SpotifyResult):
            return probe
        if probe.returncode != 0:
            return SpotifyResult(False, SpotifyErrorCode.MPRIS_UNAVAILABLE, "Spotify no está disponible.")
        identities = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
        matches = [name for name in identities if name == self._identity]
        if not matches:
            return SpotifyResult(False, SpotifyErrorCode.IDENTITY_MISSING, "Spotify no está disponible.")
        if len(matches) != 1:
            return SpotifyResult(False, SpotifyErrorCode.IDENTITY_AMBIGUOUS, "Spotify no está disponible de forma única.")
        if self._cancelled():
            return self._cancelled_result()

        control = self._run([self._bin, f"--player={self._identity}", action])
        if self._cancelled():
            return self._cancelled_result()
        if isinstance(control, SpotifyResult):
            return control
        if control.returncode != 0:
            return SpotifyResult(False, SpotifyErrorCode.CONTROL_FAILED, "No pude controlar Spotify.")
        if self._cancelled():
            return self._cancelled_result()

        status = self._run([self._bin, f"--player={self._identity}", "status"])
        if self._cancelled():
            return self._cancelled_result()
        if isinstance(status, SpotifyResult):
            return SpotifyResult(False, SpotifyErrorCode.STATE_UNKNOWN, "No pude confirmar el estado de Spotify.")
        if self._cancelled():
            return self._cancelled_result()
        state = status.stdout.strip()
        if status.returncode != 0 or state.casefold() != expected.casefold():
            return SpotifyResult(False, SpotifyErrorCode.STATE_UNKNOWN, "No pude confirmar el estado de Spotify.", state or None)
        if self._cancelled():
            return self._cancelled_result()
        return SpotifyResult(True, SpotifyErrorCode.OK, "Spotify actualizado.", state)

    def _run(self, argv: list[str]) -> Any | SpotifyResult:
        """Wait interruptibly so cancellation cannot advance a sync probe."""
        if self._operation is None:
            return self._invoke_runner(argv)
        done = threading.Event()
        result: list[Any] = []

        def invoke() -> None:
            result.append(self._invoke_runner(argv))
            done.set()

        threading.Thread(target=invoke, daemon=True).start()
        while not done.wait(0.01):
            if self._cancelled():
                return self._cancelled_result()
        return result[0]

    def _invoke_runner(self, argv: list[str]) -> Any | SpotifyResult:
        if self._runner is None:
            return self._invoke_popen(argv)
        try:
            return self._runner(
                argv, shell=False, capture_output=True, text=True,
                timeout=self._timeout, check=False,
            )
        except FileNotFoundError:
            return SpotifyResult(False, SpotifyErrorCode.BINARY_MISSING, "El control local de Spotify no está instalado.")
        except subprocess.TimeoutExpired:
            return SpotifyResult(False, SpotifyErrorCode.TIMEOUT, "El control local de Spotify tardó demasiado.")
        except OSError:
            return SpotifyResult(False, SpotifyErrorCode.MPRIS_UNAVAILABLE, "El control local de Spotify no está disponible.")

    def _invoke_popen(self, argv: list[str]) -> Any | SpotifyResult:
        """Run playerctl with a cancellable, bounded child-process wait."""
        try:
            process = subprocess.Popen(
                argv, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, start_new_session=True,
            )
        except FileNotFoundError:
            return SpotifyResult(False, SpotifyErrorCode.BINARY_MISSING, "El control local de Spotify no está instalado.")
        except OSError:
            return SpotifyResult(False, SpotifyErrorCode.MPRIS_UNAVAILABLE, "El control local de Spotify no está disponible.")

        deadline = time.monotonic() + self._timeout
        cancelled = False
        while process.poll() is None:
            if self._cancelled():
                cancelled = True
                self._stop_process(process)
                break
            if time.monotonic() >= deadline:
                self._stop_process(process)
                return SpotifyResult(False, SpotifyErrorCode.TIMEOUT, "El control local de Spotify tardó demasiado.")
            time.sleep(0.01)
        try:
            stdout, stderr = process.communicate(timeout=0.25)
        except subprocess.TimeoutExpired:
            self._stop_process(process, force=True)
            stdout, stderr = process.communicate(timeout=0.25)
        if cancelled or self._cancelled():
            return self._cancelled_result()
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)

    @staticmethod
    def _stop_process(process: Any, *, force: bool = False) -> None:
        """Terminate promptly, escalating to kill within a bounded grace period."""
        try:
            (process.kill if force else process.terminate)()
            process.wait(timeout=0.2)
        except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=0.2)
            except (OSError, ProcessLookupError, subprocess.TimeoutExpired):
                pass

    def _cancelled(self) -> bool:
        return bool(self._operation is not None and self._operation.cancelled())

    @staticmethod
    def _cancelled_result() -> SpotifyResult:
        return SpotifyResult(False, SpotifyErrorCode.CANCELLED, "")


class PlaybackCode(str, Enum):
    OK = "ok"
    NOT_AUTHORIZED = "not_authorized"
    PREMIUM_REQUIRED = "premium_required"
    TARGET_MISSING = "target_missing"
    TARGET_AMBIGUOUS = "target_ambiguous"
    UNPLAYABLE = "unplayable"
    INVALID_SELECTION = "invalid_selection"
    STATE_UNKNOWN = "state_unknown"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class PlaybackResult:
    code: PlaybackCode

    @property
    def ok(self) -> bool:
        return self.code is PlaybackCode.OK


class PlaybackOperation:
    """Volatile cancellation seam for bounded injected playback calls."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def cancelled(self) -> bool:
        return self._cancelled


class PlaybackPolicy:
    """Fail-closed policy for one verified local Spotify Desktop target."""

    ACCOUNT_URL = "https://api.spotify.com/v1/me"
    DEVICES_URL = "https://api.spotify.com/v1/me/player/devices"
    PLAY_URL = "https://api.spotify.com/v1/me/player/play"
    READBACK_URL = "https://api.spotify.com/v1/me/player"
    _ALLOWED_CONTEXTS = {"album", "artist"}

    def __init__(self, *, api: Callable[..., Any], local_identity: Callable[[], Any],
                 configured_fingerprint: str | None, scopes: Any,
                 timeout_s: float = 5.0) -> None:
        if not callable(api) or not callable(local_identity) or not 0.1 <= timeout_s <= 30.0:
            raise ValueError("invalid playback boundary")
        self._api = api
        self._local_identity = local_identity
        self._fingerprint = configured_fingerprint
        self._scopes = scopes
        self._timeout = float(timeout_s)

    def play_selection(self, catalog: CatalogClient, selection_id: str, *, session_id: str,
                       operation: Any | None = None) -> PlaybackResult:
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        selected = catalog.resolve(selection_id, session_id=session_id)
        if selected.code is not CatalogCode.SELECTED or selected.candidate is None:
            return PlaybackResult(PlaybackCode.INVALID_SELECTION)
        candidate = selected.candidate
        if (candidate.kind not in self._ALLOWED_CONTEXTS
                or not self._playable_uri(candidate.uri, candidate.kind)):
            return PlaybackResult(PlaybackCode.UNPLAYABLE)
        return self._play(candidate, operation=operation)

    def _play(self, candidate: CatalogCandidate, *, operation: Any | None = None) -> PlaybackResult:
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        if (not isinstance(candidate, CatalogCandidate)
                or candidate.kind not in self._ALLOWED_CONTEXTS
                or not self._playable_uri(candidate.uri, candidate.kind)):
            return PlaybackResult(PlaybackCode.UNPLAYABLE)
        if self._scopes != APPROVED_SPOTIFY_SCOPES:
            return PlaybackResult(PlaybackCode.NOT_AUTHORIZED)
        if not self._fingerprint:
            return PlaybackResult(PlaybackCode.TARGET_MISSING)
        try:
            identities = self._local_identity()
        except Exception:
            return PlaybackResult(PlaybackCode.TARGET_MISSING)
        if not isinstance(identities, (list, tuple)) or identities != ["spotify"]:
            return PlaybackResult(PlaybackCode.TARGET_MISSING if not identities else PlaybackCode.TARGET_AMBIGUOUS)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        try:
            account = self._api("GET", self.ACCOUNT_URL, None, self._timeout)
        except TimeoutError:
            return PlaybackResult(PlaybackCode.TIMEOUT)
        except Exception:
            return PlaybackResult(PlaybackCode.PROVIDER_ERROR)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        if not isinstance(account, dict) or account.get("product") != "premium":
            return PlaybackResult(PlaybackCode.PREMIUM_REQUIRED)
        try:
            response = self._api("GET", self.DEVICES_URL, None, self._timeout)
        except TimeoutError:
            return PlaybackResult(PlaybackCode.TIMEOUT)
        except Exception:
            return PlaybackResult(PlaybackCode.PROVIDER_ERROR)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        devices = response.get("devices", []) if isinstance(response, dict) else []
        matches = [device for device in devices if self._matches_target(device)] if isinstance(devices, list) else []
        if not matches:
            return PlaybackResult(PlaybackCode.TARGET_MISSING)
        if len(matches) != 1:
            return PlaybackResult(PlaybackCode.TARGET_AMBIGUOUS)
        device_id = matches[0].get("id")
        if not isinstance(device_id, str) or not device_id:
            return PlaybackResult(PlaybackCode.TARGET_MISSING)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        try:
            accepted = self._api("PUT", self.PLAY_URL, {
                "device_id": device_id, "context_uri": candidate.uri,
            }, self._timeout)
        except TimeoutError:
            return PlaybackResult(PlaybackCode.TIMEOUT)
        except Exception:
            return PlaybackResult(PlaybackCode.PROVIDER_ERROR)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        if not isinstance(accepted, dict) or accepted.get("accepted") is not True:
            return PlaybackResult(PlaybackCode.UNPLAYABLE)
        try:
            state = self._api("GET", self.READBACK_URL, None, self._timeout)
        except TimeoutError:
            return PlaybackResult(PlaybackCode.TIMEOUT)
        except Exception:
            return PlaybackResult(PlaybackCode.PROVIDER_ERROR)
        if self._cancelled(operation):
            return PlaybackResult(PlaybackCode.CANCELLED)
        if not self._readback_matches(state, device_id, candidate.uri):
            return PlaybackResult(PlaybackCode.STATE_UNKNOWN)
        return PlaybackResult(PlaybackCode.OK)

    def _matches_target(self, device: Any) -> bool:
        return (isinstance(device, dict) and device.get("type") == "computer"
                and device.get("fingerprint") == self._fingerprint)

    @staticmethod
    def _playable_uri(uri: Any, kind: str) -> bool:
        return isinstance(uri, str) and uri == uri.strip() and uri.startswith(f"spotify:{kind}:")

    @staticmethod
    def _readback_matches(state: Any, device_id: str, uri: str) -> bool:
        if not isinstance(state, dict) or not isinstance(state.get("device"), dict):
            return False
        item = state.get("item")
        return (state["device"].get("id") == device_id and isinstance(item, dict)
                and item.get("uri") == uri)

    @staticmethod
    def _cancelled(operation: Any | None) -> bool:
        return bool(operation is not None and callable(getattr(operation, "cancelled", None))
                    and operation.cancelled())


class CatalogCode(str, Enum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    UNSUPPORTED = "unsupported"
    INVALID_SELECTION = "invalid_selection"
    SELECTED = "selected"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True)
class CatalogCandidate:
    """Safe, in-memory catalog metadata; provider payloads never cross this boundary."""

    selection_id: str
    kind: str
    name: str
    uri: str


@dataclass(frozen=True)
class CatalogResult:
    code: CatalogCode
    candidates: tuple[CatalogCandidate, ...] = ()
    candidate: CatalogCandidate | None = None


class CatalogOperation:
    """Small injectable cancellation primitive for offline catalog calls."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def cancelled(self) -> bool:
        return self._cancelled


@dataclass
class _PendingCatalog:
    session_id: str
    candidates: dict[str, CatalogCandidate]
    expires_at: float


class CatalogClient:
    """Injected-only official Spotify catalog contract for albums and artists."""

    SEARCH_URL = "https://api.spotify.com/v1/search"
    MAX_QUERY_LENGTH = 100
    MAX_RESULTS = 10
    DEFAULT_TIMEOUT_S = 5.0

    def __init__(self, *, provider: Callable[..., Any], clock: Callable[[], float] = time.time,
                 ttl_s: float = 120.0, timeout_s: float = DEFAULT_TIMEOUT_S) -> None:
        if not callable(provider) or not 1.0 <= ttl_s <= 600.0 or not 0.1 <= timeout_s <= 30.0:
            raise ValueError("invalid catalog boundary")
        self._provider = provider
        self._clock = clock
        self._ttl_s = float(ttl_s)
        self._timeout_s = float(timeout_s)
        self._pending: _PendingCatalog | None = None
        self.playback_calls: list[Any] = []

    @property
    def pending_count(self) -> int:
        self._expire()
        return len(self._pending.candidates) if self._pending else 0

    def search(self, kind: str, query: str, *, session_id: str, limit: int = MAX_RESULTS,
               operation: Any | None = None) -> CatalogResult:
        if self._cancelled(operation):
            self.invalidate("cancelled")
            return CatalogResult(CatalogCode.CANCELLED)
        if kind not in {"album", "artist"}:
            return CatalogResult(CatalogCode.UNSUPPORTED)
        if not isinstance(query, str):
            return CatalogResult(CatalogCode.INVALID_REQUEST)
        query = query.strip()
        if not session_id or not query or len(query) > self.MAX_QUERY_LENGTH:
            return CatalogResult(CatalogCode.INVALID_REQUEST)
        bounded_limit = min(max(1, int(limit)), self.MAX_RESULTS)
        params = {"q": query, "type": kind, "limit": bounded_limit}
        try:
            response = self._provider("GET", self.SEARCH_URL, params, self._timeout_s)
        except Exception:
            self.invalidate("provider_error")
            return CatalogResult(CatalogCode.PROVIDER_ERROR)
        if self._cancelled(operation):
            self.invalidate("cancelled")
            return CatalogResult(CatalogCode.CANCELLED)
        if isinstance(response, dict):
            collection = response.get("artists" if kind == "artist" else "albums", response)
            items = collection.get("items", []) if isinstance(collection, dict) else []
        else:
            items = getattr(response, "items", [])
        if not isinstance(items, list):
            self.invalidate("invalid_response")
            return CatalogResult(CatalogCode.PROVIDER_ERROR)
        candidates = tuple(self._candidate(kind, item) for item in items[:bounded_limit])
        candidates = tuple(candidate for candidate in candidates if candidate is not None)
        self._pending = _PendingCatalog(
            session_id=session_id,
            candidates={candidate.selection_id: candidate for candidate in candidates},
            expires_at=self._clock() + self._ttl_s,
        )
        if not candidates:
            return CatalogResult(CatalogCode.NOT_FOUND)
        code = CatalogCode.SINGLE if len(candidates) == 1 else CatalogCode.MULTIPLE
        return CatalogResult(code, candidates)

    def resolve(self, selection_id: str, *, session_id: str) -> CatalogResult:
        self._expire()
        pending = self._pending
        if pending is None or pending.session_id != session_id:
            return CatalogResult(CatalogCode.INVALID_SELECTION)
        candidate = pending.candidates.pop(selection_id, None)
        if candidate is None:
            return CatalogResult(CatalogCode.INVALID_SELECTION)
        if not pending.candidates:
            self._pending = None
        return CatalogResult(CatalogCode.SELECTED, candidate=candidate)

    def invalidate(self, reason: str = "invalidated") -> None:
        self._pending = None

    def _expire(self) -> None:
        if self._pending is not None and self._clock() >= self._pending.expires_at:
            self._pending = None

    @staticmethod
    def _cancelled(operation: Any | None) -> bool:
        return bool(operation is not None and callable(getattr(operation, "cancelled", None))
                    and operation.cancelled())

    @staticmethod
    def _candidate(kind: str, item: Any) -> CatalogCandidate | None:
        if not isinstance(item, dict):
            return None
        item_id, name, uri = item.get("id"), item.get("name"), item.get("uri")
        if not all(isinstance(value, str) and value for value in (item_id, name, uri)):
            return None
        if item.get("type", kind) != kind:
            return None
        return CatalogCandidate(secrets.token_urlsafe(9), kind, name, uri)


class SpotifyService:
    """Dedicated dispatch boundary for the validated local Spotify intents."""

    _ERROR_SPEECH = {
        SpotifyErrorCode.BINARY_MISSING: "El control local de Spotify no está instalado, señor.",
        SpotifyErrorCode.TIMEOUT: "El control local de Spotify tardó demasiado, señor.",
        SpotifyErrorCode.MPRIS_UNAVAILABLE: "Spotify no está disponible localmente, señor.",
        SpotifyErrorCode.IDENTITY_MISSING: "Spotify no está disponible, señor.",
        SpotifyErrorCode.IDENTITY_AMBIGUOUS: "Spotify no está disponible de forma única, señor.",
        SpotifyErrorCode.CONTROL_FAILED: "No pude controlar Spotify, señor.",
        SpotifyErrorCode.STATE_UNKNOWN: "No pude confirmar el estado de Spotify, señor.",
        SpotifyErrorCode.CANCELLED: "",
    }

    def __init__(self, *, adapter: LocalSpotifyAdapter, enabled: bool = True) -> None:
        self._adapter = adapter
        self._enabled = enabled

    def dispatch(self, intent: Intent, session: object | None = None) -> ActionResult:
        if intent.intent not in {"spotify_play", "spotify_pause"} or intent.entities:
            return ActionResult(ok=False, spoken="Aún no sé hacer eso, señor.")
        if not self._enabled:
            return ActionResult(ok=False, spoken="El control local de Spotify está deshabilitado, señor.")

        try:
            outcome = self._adapter.play() if intent.intent == "spotify_play" else self._adapter.pause()
        except Exception:
            return ActionResult(ok=False, spoken="No pude controlar Spotify, señor.")
        if not isinstance(outcome, SpotifyResult) or not outcome.ok or outcome.code is not SpotifyErrorCode.OK:
            code = outcome.code if isinstance(outcome, SpotifyResult) else SpotifyErrorCode.CONTROL_FAILED
            return ActionResult(ok=False, spoken=self._ERROR_SPEECH.get(code, "No pude controlar Spotify, señor."))
        verb = "Reproduciendo" if intent.intent == "spotify_play" else "Pausando"
        return ActionResult(ok=True, spoken=f"{verb} Spotify, señor.")
