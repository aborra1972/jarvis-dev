"""Credential-free, Spotify-only local MPRIS control."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import secrets
import subprocess
import threading
import time
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
            "redirect_uri": "http://127.0.0.1/callback",
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
