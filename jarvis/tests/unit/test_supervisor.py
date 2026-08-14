"""Subprocess supervisor tests (PR3, task 3.4).

RF-11 lifecycle: services are started, health-checked, and restarted under a
3-restarts-per-minute backoff before being marked degraded. Processes are
faked (no real subprocesses); ``tcp_healthy`` is exercised against real
sockets for the TCP probe PR4 will reuse.
"""

from __future__ import annotations

import socket

from jarvis.orchestrator.supervisor import ProcessSpec, Supervisor, tcp_healthy


class FakeClock:
    def __init__(self) -> None:
        self._now = 0.0

    def now(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class FakeProcess:
    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy
        self.starts = 0

    def start(self) -> str:
        self.starts += 1
        return f"handle-{self.starts}"

    def is_alive(self) -> bool:
        return self._healthy


def _supervisor_with(proc, clock=None) -> Supervisor:
    sup = Supervisor(clock=clock or FakeClock())
    sup.register(ProcessSpec(name="svc", start=proc.start, is_alive=proc.is_alive))
    return sup


def test_ensure_healthy_starts_when_not_running() -> None:
    proc = FakeProcess()
    sup = _supervisor_with(proc)
    assert sup.ensure_healthy("svc") is True
    assert proc.starts == 1


def test_ensure_healthy_reports_alive_process() -> None:
    proc = FakeProcess()
    sup = _supervisor_with(proc)
    assert sup.ensure_healthy("svc") is True
    assert sup.ensure_healthy("svc") is True
    assert proc.starts == 1


def test_ensure_healthy_restarts_dead_process() -> None:
    class Reviving:
        def __init__(self) -> None:
            self.starts = 0

        def start(self) -> None:
            self.starts += 1

        def is_alive(self) -> bool:
            return self.starts >= 2

    proc = Reviving()
    sup = _supervisor_with(proc)
    assert sup.ensure_healthy("svc") is True
    assert proc.starts == 2


def test_degraded_after_three_restarts_within_window() -> None:
    clock = FakeClock()
    proc = FakeProcess(healthy=False)
    sup = _supervisor_with(proc, clock)
    for _ in range(3):
        assert sup.ensure_healthy("svc") is False
        clock.advance(1.0)
    assert proc.starts == 3
    assert sup.ensure_healthy("svc") is False
    assert sup.is_degraded("svc") is True


def test_restarts_allowed_again_after_window() -> None:
    clock = FakeClock()
    proc = FakeProcess(healthy=False)
    sup = _supervisor_with(proc, clock)
    for _ in range(3):
        sup.ensure_healthy("svc")
        clock.advance(1.0)
    assert sup.is_degraded("svc") is True
    clock.advance(61.0)
    assert sup.ensure_healthy("svc") is False
    assert sup.is_degraded("svc") is False


def test_tcp_healthy_true_when_listening() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert tcp_healthy("127.0.0.1", port, timeout=0.5) is True
    finally:
        sock.close()


def test_tcp_healthy_false_for_closed_port() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert tcp_healthy("127.0.0.1", port, timeout=0.2) is False
