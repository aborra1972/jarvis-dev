"""Subprocess supervisor (PR3, task 3.4).

Keeps PR4 services (interpreter, repo gateway) healthy: starts them on first
use, probes health, and restarts dead processes under a 3-restarts-per-minute
backoff before flagging them degraded (RF-11 lifecycle). Processes are
injected as ``ProcessSpec``; the loop wires real subprocesses, tests use fakes.
"""

from __future__ import annotations

import socket
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

MAX_RESTARTS_PER_MINUTE = 3
BACKOFF_WINDOW_S = 60.0


class RealClock:
    def now(self) -> float:
        return time.monotonic()


def tcp_healthy(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    start: Callable[[], object]
    is_alive: Callable[[], bool]
    health_timeout_s: float = 15.0


@dataclass
class ManagedProcess:
    spec: ProcessSpec
    handle: object | None = None
    restart_events: deque[float] = field(default_factory=deque)
    degraded: bool = False


class Supervisor:
    def __init__(self, clock=None) -> None:
        self._clock = clock or RealClock()
        self._managed: dict[str, ManagedProcess] = {}

    def register(self, spec: ProcessSpec) -> None:
        self._managed[spec.name] = ManagedProcess(spec=spec)

    def ensure_healthy(self, name: str) -> bool:
        proc = self._managed[name]
        if proc.handle is not None and proc.spec.is_alive():
            proc.degraded = False
            return True
        return self._start_attempt(proc)

    def is_degraded(self, name: str) -> bool:
        return self._managed[name].degraded

    def _start_attempt(self, proc: ManagedProcess) -> bool:
        now = self._clock.now()
        self._prune_restart_events(proc, now)
        if len(proc.restart_events) >= MAX_RESTARTS_PER_MINUTE:
            proc.degraded = True
            return False
        proc.restart_events.append(now)
        proc.handle = proc.spec.start()
        if proc.spec.is_alive():
            return True
        return self._restart_attempt(proc)

    def _restart_attempt(self, proc: ManagedProcess) -> bool:
        now = self._clock.now()
        self._prune_restart_events(proc, now)
        if len(proc.restart_events) >= MAX_RESTARTS_PER_MINUTE:
            proc.degraded = True
            return False
        proc.restart_events.append(now)
        proc.handle = proc.spec.start()
        return proc.spec.is_alive()

    def _prune_restart_events(self, proc: ManagedProcess, now: float) -> None:
        while proc.restart_events and now - proc.restart_events[0] > BACKOFF_WINDOW_S:
            proc.restart_events.popleft()
        if not proc.restart_events:
            proc.degraded = False
