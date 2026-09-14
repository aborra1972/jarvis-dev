from dataclasses import dataclass

import pytest

from jarvis.services.spotify import (
    APPROVED_SPOTIFY_SCOPES,
    CatalogClient,
    PlaybackCode,
    PlaybackOperation,
    PlaybackPolicy,
)


@dataclass
class FakeApi:
    account: dict
    devices: list[dict]
    readback: dict | None = None

    def __post_init__(self):
        self.calls = []

    def __call__(self, method, url, payload, timeout):
        self.calls.append((method, url, payload, timeout))
        if url.endswith("/me"):
            return self.account
        if url.endswith("/me/player/devices"):
            return {"devices": self.devices}
        if url.endswith("/me/player/play"):
            return {"accepted": True}
        if url.endswith("/me/player"):
            return self.readback
        raise AssertionError(url)


def candidate_catalog(uri="spotify:artist:a1"):
    def provider(*_args):
        return {"artists": {"items": [{"id": "a1", "name": "Björk", "uri": uri, "type": "artist"}]}}

    catalog = CatalogClient(provider=provider, clock=lambda: 100.0)
    result = catalog.search("artist", "Björk", session_id="s1")
    return catalog, result.candidates[0].selection_id


def ready_policy(api, *, local=None, fingerprint="desktop-1", scopes=None):
    return PlaybackPolicy(
        api=api,
        local_identity=local or (lambda: ["spotify"]),
        configured_fingerprint=fingerprint,
        scopes=APPROVED_SPOTIFY_SCOPES if scopes is None else scopes,
        timeout_s=2.0,
    )


def test_play_selection_requires_all_readiness_gates_and_reads_back_target():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "volatile-id", "name": "Jarvis Desktop", "type": "computer", "is_active": True,
          "fingerprint": "desktop-1"}],
        {"device": {"id": "volatile-id", "type": "computer"}, "item": {"uri": "spotify:artist:a1"}},
    )
    policy = ready_policy(api)
    catalog, selection = candidate_catalog()

    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is PlaybackCode.OK
    assert [call[0:3] for call in api.calls] == [
        ("GET", "https://api.spotify.com/v1/me", None),
        ("GET", "https://api.spotify.com/v1/me/player/devices", None),
        ("PUT", "https://api.spotify.com/v1/me/player/play",
         {"device_id": "volatile-id", "context_uri": "spotify:artist:a1"}),
        ("GET", "https://api.spotify.com/v1/me/player", None),
    ]


@pytest.mark.parametrize(
    "account,devices,local,scopes,expected",
    [
        ({"product": "free"}, [], ["spotify"], APPROVED_SPOTIFY_SCOPES, PlaybackCode.PREMIUM_REQUIRED),
        ({"product": "premium"}, [], ["spotify"], {"user-read-playback-state"}, PlaybackCode.NOT_AUTHORIZED),
        ({"product": "premium"}, [], [], APPROVED_SPOTIFY_SCOPES, PlaybackCode.TARGET_MISSING),
        ({"product": "premium"}, [
            {"id": "a", "name": "one", "type": "computer", "fingerprint": "desktop-1"},
            {"id": "b", "name": "two", "type": "computer", "fingerprint": "desktop-1"},
        ], ["spotify"], APPROVED_SPOTIFY_SCOPES, PlaybackCode.TARGET_AMBIGUOUS),
        ({"product": "premium"}, [{"id": "a", "type": "mobile", "fingerprint": "desktop-1"}], ["spotify"], APPROVED_SPOTIFY_SCOPES, PlaybackCode.TARGET_MISSING),
    ],
)
def test_policy_fails_closed_before_playback(account, devices, local, scopes, expected):
    api = FakeApi(account, devices)
    policy = ready_policy(api, local=lambda: local, scopes=scopes)
    catalog, selection = candidate_catalog()

    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is expected
    assert not any(call[1].endswith("/play") for call in api.calls)


def test_policy_rejects_unknown_selection_without_provider_or_local_call():
    api = FakeApi({"product": "premium"}, [])
    local_calls = []
    policy = ready_policy(api, local=lambda: local_calls.append(1) or ["spotify"])
    catalog, _ = candidate_catalog()

    result = policy.play_selection(catalog, "unknown", session_id="s1")

    assert result.code is PlaybackCode.INVALID_SELECTION
    assert api.calls == []
    assert local_calls == []


def test_policy_rejects_unplayable_candidate_and_never_uses_transfer_or_fallback():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "a", "type": "computer", "fingerprint": "desktop-1"}],
    )
    policy = ready_policy(api)
    catalog, selection = candidate_catalog(uri="spotify:playlist:not-approved")

    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is PlaybackCode.UNPLAYABLE
    assert not any(call[1].endswith("/play") for call in api.calls)


def test_unknown_readback_is_not_reported_as_success():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "a", "type": "computer", "fingerprint": "desktop-1"}],
        None,
    )
    policy = ready_policy(api)
    catalog, selection = candidate_catalog()

    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is PlaybackCode.STATE_UNKNOWN


def test_oauth_playback_bridge_uses_fixed_api_and_normalizes_no_content():
    from jarvis.services.spotify import SpotifyPlaybackBridge, OAuthErrorCode, OAuthResult
    calls = []
    class OAuth:
        def request(self, method, url, payload):
            calls.append((method, url, payload))
            return OAuthResult(OAuthErrorCode.OK, "", payload={"product": "premium"})
    bridge = SpotifyPlaybackBridge(oauth=OAuth())
    assert bridge("GET", "https://api.spotify.com/v1/me", None, 2.0) == {"product": "premium"}
    assert calls == [("GET", "https://api.spotify.com/v1/me", None)]


def test_cancellation_prevents_playback_and_readback():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "a", "type": "computer", "fingerprint": "desktop-1"}],
    )
    operation = PlaybackOperation()
    operation.cancel()
    policy = ready_policy(api)
    catalog, selection = candidate_catalog()

    result = policy.play_selection(catalog, selection, session_id="s1", operation=operation)

    assert result.code is PlaybackCode.CANCELLED
    assert api.calls == []
