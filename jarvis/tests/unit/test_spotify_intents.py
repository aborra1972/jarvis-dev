from __future__ import annotations

from dataclasses import dataclass

import pytest

from jarvis.actions import base
from jarvis.interpreter.golden import gate
from jarvis.interpreter.interpreter import resolve_intent
from jarvis.interpreter.normalize import normalize
from jarvis.interpreter.schema import Intent, SchemaError, validate
from jarvis.services.spotify import CatalogCandidate, CatalogCode, CatalogResult


def intent_from(raw: str):
    return gate(normalize(raw))


@pytest.mark.parametrize(
    ("raw", "kind", "query"),
    [
        ("buscá el álbum bocanada", "album", "bocanada"),
        ("buscar la artista björk", "artist", "bjork"),
        ("buscá artistas soda stereo", "artist", "soda stereo"),
    ],
)
def test_spanish_search_forms_are_deterministic(raw: str, kind: str, query: str) -> None:
    result = intent_from(raw)
    assert result is not None
    assert result.intent == "spotify_search"
    assert result.entities == {"kind": kind, "query": query}


@pytest.mark.parametrize(
    ("raw", "selector"),
    [
        ("reproducí el primero", "1"),
        ("elegí la segunda", "2"),
        ("reproducí selección AbC_123-x", "abc_123-x"),
    ],
)
def test_selection_accepts_only_numeric_or_opaque_pending_reference(raw: str, selector: str) -> None:
    result = intent_from(raw)
    assert result is not None
    assert result.intent == "spotify_play_selection"
    assert result.entities == {"selection_id": selector}


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "spotify_search", "entities": {"kind": "playlist", "query": "x"}},
        {"intent": "spotify_search", "entities": {"kind": "album", "query": "spotify:album:x"}},
        {"intent": "spotify_play_selection", "entities": {"selection_id": "spotify:track:x"}},
        {"intent": "spotify_play_selection", "entities": {"selection_id": "1", "device_id": "other"}},
        {"intent": "spotify_search", "entities": {"kind": "artist", "query": "x", "uri": "spotify:artist:x"}},
    ],
)
def test_provider_device_uri_and_unsupported_entities_are_rejected(payload: dict) -> None:
    with pytest.raises(SchemaError):
        validate(payload)


@pytest.mark.parametrize(
    "raw",
    [
        "dale play",
        "dale play spotify",
        "poné música",
        "pone musica",
        "reproducí",
        "reproduce",
        "play spotify",
        "reproducir spotify",
    ],
)
def test_natural_spotify_play_aliases_are_deterministic(raw: str) -> None:
    result = intent_from(raw)
    assert result is not None
    assert result.intent == "spotify_play"
    assert result.entities == {}


@pytest.mark.parametrize(
    "raw",
    ["pausá", "pausa", "pause spotify", "pausar spotify", "pará la música", "para la musica"],
)
def test_natural_spotify_pause_aliases_are_deterministic(raw: str) -> None:
    result = intent_from(raw)
    assert result is not None
    assert result.intent == "spotify_pause"
    assert result.entities == {}


def test_spotify_control_does_not_combine_with_open_app_text() -> None:
    assert intent_from("abrí Spotify y dale play").intent == "open_app"
    assert intent_from("abrí Spotify y pausá").intent == "open_app"


def test_search_and_selection_never_fall_through_to_generic_execute() -> None:
    assert "spotify_search" not in base.build_registry().handlers()
    assert "spotify_play_selection" not in base.build_registry().handlers()
    assert intent_from("buscá el álbum bocanada").intent != "execute"
    assert intent_from("reproducí el segundo").intent != "execute"


def test_llm_search_payload_is_validated_and_dedicated() -> None:
    from jarvis.interpreter.llm import FakeProvider

    result = resolve_intent(
        "encontrá el álbum bocanada",
        provider=FakeProvider([{
            "intent": "spotify_search",
            "entities": {"kind": "album", "query": "bocanada"},
            "confidence": 0.9,
        }]),
        use_cache=False,
    )
    assert result.intent is not None
    assert result.intent.intent == "spotify_search"
    assert result.intent.intent != "execute"


@dataclass
class Session:
    session_id: str


class FakeCatalog:
    def __init__(self, result: CatalogResult) -> None:
        self.result = result
        self.calls: list[tuple] = []

    def search(self, kind: str, query: str, *, session_id: str):
        self.calls.append(("search", kind, query, session_id))
        return self.result

    def resolve(self, selection_id: str, *, session_id: str):
        self.calls.append(("resolve", selection_id, session_id))
        return self.result


def test_catalog_intents_use_dedicated_injected_boundary_and_safe_data() -> None:
    candidate = CatalogCandidate("opaque_123", "album", "Bocanada", "spotify:album:secret")
    catalog = FakeCatalog(CatalogResult(CatalogCode.SINGLE, (candidate,)))
    registry = base.build_registry(catalog_client=catalog)

    searched = registry.execute(
        Intent("spotify_search", {"kind": "album", "query": "bocanada"}, confidence=1.0),
        Session("session-1"),
    )
    assert searched.ok is True
    assert searched.data == {"selection_id": "opaque_123", "kind": "album", "name": "Bocanada"}
    assert "spotify:album:secret" not in searched.spoken
    assert catalog.calls == [("search", "album", "bocanada", "session-1")]


def test_numeric_and_exact_selection_reach_catalog_without_provider_fields() -> None:
    candidate = CatalogCandidate("opaque_123", "artist", "Björk", "spotify:artist:secret")
    catalog = FakeCatalog(CatalogResult(CatalogCode.SELECTED, candidate=candidate))
    registry = base.build_registry(catalog_client=catalog)

    result = registry.execute(
        Intent("spotify_play_selection", {"selection_id": "2"}, confidence=1.0),
        Session("session-1"),
    )
    assert result.ok is True
    assert catalog.calls == [("resolve", "2", "session-1")]
    assert "spotify:artist:secret" not in result.spoken
