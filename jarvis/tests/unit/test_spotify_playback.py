from dataclasses import dataclass
from urllib.parse import urlsplit

import pytest

from jarvis.services.spotify import (
    APPROVED_SPOTIFY_SCOPES,
    CatalogClient,
    PlaybackCode,
    PlaybackOperation,
    PlaybackPolicy,
    SpotifyPlaybackHTTPError,
    spotify_device_fingerprint,
)


@dataclass
class FakeApi:
    account: dict
    devices: list[dict]
    readback: dict | None = None
    play_error: Exception | None = None

    def __post_init__(self):
        self.calls = []

    def __call__(self, method, url, payload, timeout):
        self.calls.append((method, url, payload, timeout))
        if url.endswith("/me"):
            return self.account
        if url.endswith("/me/player/devices"):
            return {"devices": self.devices}
        if urlsplit(url).path.endswith("/me/player/play"):
            if self.play_error is not None:
                raise self.play_error
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


def ready_policy(api, *, local=None, fingerprint=None, scopes=None):
    return PlaybackPolicy(
        api=api,
        local_identity=local or (lambda: ["spotify"]),
        configured_fingerprint=(spotify_device_fingerprint(api.devices[0]["id"])
                               if fingerprint is None and api.devices else
                               (fingerprint or spotify_device_fingerprint("volatile-id"))),
        scopes=APPROVED_SPOTIFY_SCOPES if scopes is None else scopes,
        timeout_s=2.0,
    )


def test_device_fingerprint_is_domain_separated_and_requires_nonempty_id():
    assert spotify_device_fingerprint("volatile-id") == spotify_device_fingerprint("volatile-id")
    assert len(spotify_device_fingerprint("volatile-id")) == 64
    assert spotify_device_fingerprint("volatile-id") != __import__("hashlib").sha256(b"volatile-id").hexdigest()
    with pytest.raises(ValueError):
        spotify_device_fingerprint("")
    with pytest.raises(ValueError):
        spotify_device_fingerprint(" volatile-id")


def test_policy_accepts_spotify_standard_computer_type():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "standard-computer-id", "type": "Computer"}],
    )
    policy = ready_policy(api)

    assert policy._matches_target(api.devices[0])


@pytest.mark.parametrize("device_type", ["Smartphone", "Speaker", "COMPUTER", "computerized", "unknown"])
def test_policy_rejects_non_computer_device_types(device_type):
    api = FakeApi(
        {"product": "premium"},
        [{"id": "device-id", "type": device_type}],
    )
    policy = ready_policy(api)

    assert not policy._matches_target(api.devices[0])


def test_play_selection_requires_all_readiness_gates_and_reads_back_target():
    api = FakeApi(
        {"product": "premium"},
        [{"id": "volatile-id", "name": "Jarvis Desktop", "type": "computer", "is_active": True}],
        {
            "device": {"id": "volatile-id", "type": "computer"},
            "context": {"uri": "spotify:artist:a1"},
            "item": {"uri": "spotify:track:come-together"},
        },
    )
    policy = ready_policy(api)
    catalog, selection = candidate_catalog()

    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is PlaybackCode.OK
    assert [call[0:3] for call in api.calls] == [
        ("GET", "https://api.spotify.com/v1/me/player/devices", None),
        ("PUT", "https://api.spotify.com/v1/me/player/play?device_id=volatile-id",
         {"context_uri": "spotify:artist:a1"}),
        ("GET", "https://api.spotify.com/v1/me/player", None),
    ]


@pytest.mark.parametrize(
    "account,devices,local,scopes,expected",
    [
        ({}, [], ["spotify"], {"user-read-playback-state"}, PlaybackCode.NOT_AUTHORIZED),
        ({"product": "premium"}, [], ["spotify"], {"user-read-playback-state"}, PlaybackCode.NOT_AUTHORIZED),
        ({"product": "premium"}, [], [], APPROVED_SPOTIFY_SCOPES, PlaybackCode.TARGET_MISSING),
        ({"product": "premium"}, [
            {"id": "a", "name": "one", "type": "computer", "fingerprint": "desktop-1"},
            {"id": "a", "name": "two", "type": "computer", "fingerprint": "desktop-1"},
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


def test_spotify_403_is_the_only_playback_premium_signal():
    api = FakeApi({}, [{"id": "volatile-id", "type": "Computer"}],
                  play_error=SpotifyPlaybackHTTPError("spotify_http_403"))
    policy = ready_policy(api)
    catalog, selection = candidate_catalog()
    result = policy.play_selection(catalog, selection, session_id="s1")

    assert result.code is PlaybackCode.PREMIUM_REQUIRED


@pytest.mark.parametrize(
    "readback",
    [
        {"device": {"id": "other-device"}, "context": {"uri": "spotify:album:abbey-road"}},
        {"device": {"id": "device-id"}},
        {"device": {"id": "device-id"}, "context": {"uri": "spotify:album:let-it-be"}},
    ],
)
def test_readback_requires_exact_device_and_context_uri(readback):
    assert not PlaybackPolicy._readback_matches(
        readback, "device-id", "spotify:album:abbey-road"
    )


def test_readback_matches_album_context_even_when_track_item_differs():
    assert PlaybackPolicy._readback_matches(
        {
            "device": {"id": "device-id"},
            "context": {"uri": "spotify:album:abbey-road"},
            "item": {"uri": "spotify:track:come-together"},
        },
        "device-id",
        "spotify:album:abbey-road",
    )


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
            return OAuthResult(OAuthErrorCode.OK, "", payload={"devices": []})
    bridge = SpotifyPlaybackBridge(oauth=OAuth())
    assert bridge("GET", "https://api.spotify.com/v1/me/player/devices", None, 2.0) == {"devices": []}
    assert bridge("PUT", "https://api.spotify.com/v1/me/player/play?device_id=opaque-device",
                  {"context_uri": "spotify:artist:opaque"}, 2.0) == {"accepted": True}
    assert calls == [
        ("GET", "https://api.spotify.com/v1/me/player/devices", None),
        ("PUT", "https://api.spotify.com/v1/me/player/play?device_id=opaque-device",
         {"context_uri": "spotify:artist:opaque"}),
    ]


def test_playback_bridge_exposes_only_bounded_403_category():
    from jarvis.services.spotify import SpotifyPlaybackBridge, OAuthErrorCode, OAuthResult

    class OAuth:
        def request(self, method, url, payload):
            return OAuthResult(OAuthErrorCode.PROVIDER_ERROR, "", diagnostic="spotify_http_403",
                               payload={"secret": "must not escape"})

    bridge = SpotifyPlaybackBridge(oauth=OAuth())
    with pytest.raises(SpotifyPlaybackHTTPError, match="spotify_http_403"):
        bridge("PUT", "https://api.spotify.com/v1/me/player/play?device_id=opaque-device",
               {"context_uri": "spotify:artist:opaque"}, 2.0)


def test_playback_bridge_keeps_401_unauthorized_fail_closed():
    from jarvis.services.spotify import SpotifyPlaybackBridge, OAuthErrorCode, OAuthResult

    class OAuth:
        def request(self, method, url, payload):
            return OAuthResult(OAuthErrorCode.UNAUTHORIZED, "", diagnostic="spotify_http_401")

    bridge = SpotifyPlaybackBridge(oauth=OAuth())
    with pytest.raises(RuntimeError):
        bridge("PUT", "https://api.spotify.com/v1/me/player/play?device_id=opaque-device",
               {"context_uri": "spotify:artist:opaque"}, 2.0)


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
