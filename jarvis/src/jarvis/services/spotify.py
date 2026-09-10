"""Credential-free, Spotify-only local MPRIS control."""

from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import dataclass
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
