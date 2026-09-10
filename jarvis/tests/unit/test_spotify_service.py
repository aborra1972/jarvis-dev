from __future__ import annotations

from jarvis.orchestrator.contracts import ActionResult
from jarvis.interpreter.schema import Intent
from jarvis.services.spotify import LocalSpotifyAdapter, SpotifyErrorCode, SpotifyResult, SpotifyService


def intent(name: str) -> Intent:
    return Intent(intent=name, entities={}, confidence=1.0)


def result(code: SpotifyErrorCode, ok: bool = False) -> SpotifyResult:
    return SpotifyResult(ok=ok, code=code, message="adapter detail")


class FakeAdapter:
    def __init__(self, outcome: SpotifyResult):
        self.outcome = outcome
        self.calls: list[str] = []

    def play(self):
        self.calls.append("play")
        return self.outcome

    def pause(self):
        self.calls.append("pause")
        return self.outcome


def test_only_validated_spotify_intents_reach_the_adapter():
    adapter = FakeAdapter(result(SpotifyErrorCode.OK, ok=True))
    service = SpotifyService(adapter=adapter)

    assert service.dispatch(intent("spotify_play")).ok is True
    assert service.dispatch(intent("spotify_pause")).ok is True
    rejected = service.dispatch(intent("execute"))

    assert adapter.calls == ["play", "pause"]
    assert rejected == ActionResult(ok=False, spoken="Aún no sé hacer eso, señor.")


def test_disabled_spotify_is_recoverable_without_adapter_call():
    adapter = FakeAdapter(result(SpotifyErrorCode.OK, ok=True))
    response = SpotifyService(adapter=adapter, enabled=False).dispatch(intent("spotify_play"))

    assert response.ok is False
    assert "deshabilitado" in response.spoken
    assert adapter.calls == []


def test_failures_never_claim_success_and_are_safely_mapped():
    for code in SpotifyErrorCode:
        adapter = FakeAdapter(result(code, ok=code is SpotifyErrorCode.OK))
        response = SpotifyService(adapter=adapter).dispatch(intent("spotify_play"))
        if code is SpotifyErrorCode.OK:
            assert response.ok is True
            assert "Reproduciendo" in response.spoken
        else:
            assert response.ok is False
            assert "adapter detail" not in response.spoken


def test_service_does_not_accept_an_arbitrary_adapter_command():
    adapter = FakeAdapter(result(SpotifyErrorCode.OK, ok=True))
    service = SpotifyService(adapter=adapter)

    response = service.dispatch(Intent(intent="spotify_play", entities={"command": "playerctl pause"}, confidence=1.0))

    assert response.ok is False
    assert adapter.calls == []


def test_registry_spotify_handlers_use_dedicated_service(monkeypatch):
    from jarvis.actions import base

    adapter = FakeAdapter(result(SpotifyErrorCode.OK, ok=True))
    registry = base.build_registry(spotify_adapter=adapter)

    assert registry.execute(intent("spotify_play"), object()).ok is True
    assert adapter.calls == ["play"]
    assert registry.handlers()["spotify_play"].__self__.__class__ is SpotifyService
    assert isinstance(registry.handlers()["spotify_play"].__self__._adapter, LocalSpotifyAdapter) is False
