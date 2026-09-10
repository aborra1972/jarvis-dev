from __future__ import annotations

import subprocess

import pytest

from jarvis.orchestrator.contracts import OperationToken
from jarvis.services.spotify import LocalSpotifyAdapter, SpotifyErrorCode


class FakeRunner:
    def __init__(self, results=None, *, cancel=None):
        self.results = list(results or [])
        self.calls = []
        self.cancel = cancel

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if self.cancel:
            self.cancel(len(self.calls))
        item = self.results.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def completed(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="secret stderr")


def adapter(runner, token=None):
    return LocalSpotifyAdapter(runner=runner, operation=token, timeout_s=1.25)


def test_play_uses_fixed_spotify_argv_and_verifies_state():
    runner = FakeRunner([completed("spotify\n"), completed(), completed("Playing\n")])
    result = adapter(runner).play()

    assert result.ok is True
    assert result.code is SpotifyErrorCode.OK
    assert [call[0] for call in runner.calls] == [
        ["playerctl", "-l"],
        ["playerctl", "--player=spotify", "play"],
        ["playerctl", "--player=spotify", "status"],
    ]
    assert all(call[1]["shell"] is False for call in runner.calls)
    assert all(call[1]["timeout"] == 1.25 for call in runner.calls)


def test_nonzero_probe_with_spotify_output_fails_closed_without_control():
    runner = FakeRunner([completed("spotify\\n", returncode=1)])

    result = adapter(runner).play()

    assert result.ok is False
    assert result.code is SpotifyErrorCode.MPRIS_UNAVAILABLE
    assert len(runner.calls) == 1
    assert runner.calls[0][0] == ["playerctl", "-l"]


def test_pause_requires_exactly_one_spotify_identity():
    for listing, code in [("", SpotifyErrorCode.IDENTITY_MISSING), ("spotify\nspotify\n", SpotifyErrorCode.IDENTITY_AMBIGUOUS), ("vlc\n", SpotifyErrorCode.IDENTITY_MISSING)]:
        runner = FakeRunner([completed(listing)])
        result = adapter(runner).pause()
        assert result.code is code and result.ok is False
        assert len(runner.calls) == 1


def test_control_failure_and_unknown_state_never_claim_success():
    failed = adapter(FakeRunner([completed("spotify\n"), completed(returncode=1)])).play()
    unknown = adapter(FakeRunner([completed("spotify\n"), completed(), completed("Playing\n")])).pause()
    assert failed.code is SpotifyErrorCode.CONTROL_FAILED and not failed.ok
    assert unknown.code is SpotifyErrorCode.STATE_UNKNOWN and not unknown.ok
    assert "secret" not in failed.message + unknown.message


@pytest.mark.parametrize("exc, code", [
    (FileNotFoundError(), SpotifyErrorCode.BINARY_MISSING),
    (subprocess.TimeoutExpired(["playerctl"], 1), SpotifyErrorCode.TIMEOUT),
])
def test_runner_failures_are_typed_and_redacted(exc, code):
    result = adapter(FakeRunner([exc])).play()
    assert result.code is code
    assert result.ok is False
    assert "playerctl" not in result.message


def test_cancellation_before_probe_control_and_return():
    token = OperationToken()
    first = FakeRunner([completed("spotify\n")], cancel=lambda n: token.cancel("off") if n == 1 else None)
    assert adapter(first, token).play().code is SpotifyErrorCode.CANCELLED
    assert len(first.calls) == 1

    token = OperationToken()
    control = FakeRunner([completed("spotify\n"), completed("Playing\n")], cancel=lambda n: token.cancel("off") if n == 1 else None)
    assert adapter(control, token).play().code is SpotifyErrorCode.CANCELLED
    assert len(control.calls) == 1

    token.cancel("off")
    untouched = FakeRunner()
    assert adapter(untouched, token).play().code is SpotifyErrorCode.CANCELLED
    assert untouched.calls == []

    token = OperationToken()
    late = FakeRunner([completed("spotify\n"), completed(), completed("Playing\n")], cancel=lambda n: token.cancel("off") if n == 3 else None)
    assert adapter(late, token).play().code is SpotifyErrorCode.CANCELLED


def test_status_nonzero_is_unknown_and_stderr_is_not_exposed():
    result = adapter(FakeRunner([completed("spotify\n"), completed(returncode=0), completed(returncode=2)])).play()
    assert result.code is SpotifyErrorCode.STATE_UNKNOWN
    assert "secret stderr" not in result.message
