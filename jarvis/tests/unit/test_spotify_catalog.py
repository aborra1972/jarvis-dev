from dataclasses import dataclass

import pytest

from jarvis.services.spotify import (
    CatalogBridgeCode,
    CatalogCode,
    CatalogClient,
    CatalogOperation,
    OAuthErrorCode,
    OAuthResult,
    SpotifyCatalogBridge,
)


@dataclass
class FakeResponse:
    items: list[dict]


class FakeProvider:
    def __init__(self, items=None):
        self.items = items or []
        self.calls = []
        self.official_envelope = False

    def __call__(self, method, url, params, timeout):
        self.calls.append((method, url, params, timeout))
        if self.official_envelope:
            return {params["type"] + "s": {"items": self.items}}
        return FakeResponse(self.items)


class FakeOperation:
    def __init__(self):
        self.cancelled_flag = False

    def cancelled(self):
        return self.cancelled_flag


def item(kind="artist", item_id="artist-1", name="Björk"):
    return {"id": item_id, "name": name, "uri": f"spotify:{kind}:{item_id}", "type": kind}


def test_search_uses_bounded_official_endpoint_and_normalizes_single_result():
    provider = FakeProvider([item()])
    client = CatalogClient(provider=provider, clock=lambda: 100.0, ttl_s=30.0)

    result = client.search("artist", "  Björk  ", session_id="s1", limit=99)

    assert result.code is CatalogCode.SINGLE
    assert result.candidates[0].name == "Björk"
    assert result.candidates[0].selection_id
    assert provider.calls == [
        ("GET", "https://api.spotify.com/v1/search",
         {"q": "Björk", "type": "artist", "limit": 10}, 5.0)
    ]


def test_official_response_envelope_is_normalized_without_retaining_payload():
    provider = FakeProvider([item()])
    provider.official_envelope = True
    client = CatalogClient(provider=provider, clock=lambda: 100.0)

    result = client.search("artist", "Björk", session_id="s1")

    assert result.code is CatalogCode.SINGLE
    assert result.candidates[0].uri == "spotify:artist:artist-1"


def test_search_normalizes_no_and_multiple_without_playback_contract():
    provider = FakeProvider([item(item_id="a"), item(item_id="b", name="Björk live")])
    client = CatalogClient(provider=provider, clock=lambda: 100.0)

    multiple = client.search("artist", "Björk", session_id="s1")
    assert multiple.code is CatalogCode.MULTIPLE
    assert len(multiple.candidates) == 2
    assert client.playback_calls == []

    provider.items = []
    none = client.search("artist", "unknown", session_id="s1")
    assert none.code is CatalogCode.NOT_FOUND
    assert none.candidates == ()
    assert client.playback_calls == []


def test_search_rejects_unsupported_or_oversized_queries_without_provider_call():
    provider = FakeProvider([item()])
    client = CatalogClient(provider=provider, clock=lambda: 100.0)

    assert client.search("track", "x", session_id="s1").code is CatalogCode.UNSUPPORTED
    assert client.search("album", "x" * 101, session_id="s1").code is CatalogCode.INVALID_REQUEST
    assert client.search("album", "   ", session_id="s1").code is CatalogCode.INVALID_REQUEST
    assert provider.calls == []


def test_selection_is_opaque_session_bound_short_lived_and_one_time():
    provider = FakeProvider([item()])
    client = CatalogClient(provider=provider, clock=lambda: 100.0, ttl_s=30.0)
    result = client.search("artist", "Björk", session_id="s1")
    selection_id = result.candidates[0].selection_id

    assert selection_id != "artist-1"
    assert client.resolve(selection_id, session_id="other").code is CatalogCode.INVALID_SELECTION
    assert client.resolve(selection_id, session_id="s1").code is CatalogCode.SELECTED
    assert client.resolve(selection_id, session_id="s1").code is CatalogCode.INVALID_SELECTION


def test_replacement_expiry_off_and_cancellation_invalidate_pending_selection():
    now = [100.0]
    provider = FakeProvider([item()])
    client = CatalogClient(provider=provider, clock=lambda: now[0], ttl_s=30.0)

    first = client.search("artist", "one", session_id="s1")
    second = client.search("artist", "two", session_id="s1")
    assert client.resolve(first.candidates[0].selection_id, session_id="s1").code is CatalogCode.INVALID_SELECTION

    now[0] = 130.0
    assert client.resolve(second.candidates[0].selection_id, session_id="s1").code is CatalogCode.INVALID_SELECTION

    third = client.search("artist", "three", session_id="s1")
    client.invalidate("off")
    assert client.resolve(third.candidates[0].selection_id, session_id="s1").code is CatalogCode.INVALID_SELECTION

    operation = FakeOperation()
    operation.cancelled_flag = True
    cancelled = client.search("artist", "four", session_id="s1", operation=operation)
    assert cancelled.code is CatalogCode.CANCELLED
    assert client.resolve(third.candidates[0].selection_id, session_id="s1").code is CatalogCode.INVALID_SELECTION


def test_provider_payload_is_discarded_and_malformed_items_are_not_selections():
    provider = FakeProvider([item(), {"name": "missing id"}, {"id": "", "name": "empty"}])
    client = CatalogClient(provider=provider, clock=lambda: 100.0)

    result = client.search("artist", "query", session_id="s1")

    assert result.code is CatalogCode.SINGLE
    assert len(result.candidates) == 1
    assert not hasattr(result.candidates[0], "payload")
    resolved = client.resolve(result.candidates[0].selection_id, session_id="s1")
    assert resolved.candidate.uri == "spotify:artist:artist-1"


def test_catalog_operation_is_bounded_and_cancellation_does_not_store_results():
    provider = FakeProvider([item()])
    operation = CatalogOperation()
    client = CatalogClient(provider=provider, clock=lambda: 100.0)
    operation.cancel()

    result = client.search("artist", "query", session_id="s1", operation=operation)

    assert result.code is CatalogCode.CANCELLED
    assert client.pending_count == 0


def bridge_response(items, status=200):
    return type("Response", (), {
        "status_code": status,
        "json": lambda self: {"artists": {"items": items}},
    })()


class FakeOAuth:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def access_token(self):
        self.calls += 1
        return self.result


def test_bridge_gets_token_and_uses_bounded_bearer_search_transport():
    calls = []
    oauth = FakeOAuth(OAuthResult(OAuthErrorCode.OK, "", access_token="secret-token"))

    def transport(method, url, params, headers, timeout):
        calls.append((method, url, params, headers, timeout))
        return bridge_response([item()])

    bridge = SpotifyCatalogBridge(oauth=oauth, transport=transport, timeout_s=2.0)
    result = bridge.search("artist", "  Björk  ", session_id="s1", limit=99)

    assert result.code is CatalogBridgeCode.OK
    assert result.catalog is not None and result.catalog.code is CatalogCode.SINGLE
    assert calls == [("GET", "https://api.spotify.com/v1/search",
                      {"q": "Björk", "type": "artist", "limit": 10},
                      {"Authorization": "Bearer secret-token"}, 2.0)]
    assert "secret-token" not in repr(result)


def test_bridge_rejects_unsupported_and_does_not_call_transport():
    calls = []
    bridge = SpotifyCatalogBridge(
        oauth=FakeOAuth(OAuthResult(OAuthErrorCode.OK, "", access_token="token")),
        transport=lambda *args: calls.append(args),
    )
    result = bridge.search("track", "x", session_id="s1")
    assert result.code is CatalogBridgeCode.UNSUPPORTED
    assert calls == []


@pytest.mark.parametrize(("oauth_code", "bridge_code"), [
    (OAuthErrorCode.DISABLED, CatalogBridgeCode.DISABLED),
    (OAuthErrorCode.NOT_AUTHORIZED, CatalogBridgeCode.UNAUTHORIZED),
    (OAuthErrorCode.STORAGE_UNAVAILABLE, CatalogBridgeCode.STORAGE_UNAVAILABLE),
    (OAuthErrorCode.NETWORK_TIMEOUT, CatalogBridgeCode.TIMEOUT),
])
def test_bridge_maps_oauth_failures_without_transport(oauth_code, bridge_code):
    calls = []
    bridge = SpotifyCatalogBridge(
        oauth=FakeOAuth(OAuthResult(oauth_code, "provider detail")),
        transport=lambda *args: calls.append(args),
    )
    result = bridge.search("artist", "query", session_id="s1")
    assert result.code is bridge_code
    assert calls == []
    assert "provider detail" not in repr(result)


def test_bridge_maps_401_timeout_and_provider_failure_without_leaking_payload():
    for response_or_error, expected in [
        (bridge_response([], status=401), CatalogBridgeCode.API_UNAUTHORIZED),
        (TimeoutError("token secret query"), CatalogBridgeCode.TIMEOUT),
        (RuntimeError("raw provider payload"), CatalogBridgeCode.PROVIDER_ERROR),
    ]:
        def transport(*args, value=response_or_error):
            if isinstance(value, BaseException):
                raise value
            return value

        bridge = SpotifyCatalogBridge(
            oauth=FakeOAuth(OAuthResult(OAuthErrorCode.OK, "", access_token="secret")),
            transport=transport,
        )
        result = bridge.search("artist", "private query", session_id="s1")
        assert result.code is expected
        assert result.catalog is None
        assert "secret" not in repr(result)
        assert "private query" not in repr(result)
        assert "raw provider payload" not in repr(result)
