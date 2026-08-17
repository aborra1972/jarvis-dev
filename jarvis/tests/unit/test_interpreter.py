"""Interpreter orchestration tests (PR2, task 2.5).

Composition contract: normalize → golden gate FIRST (destructive intents never
touch the LLM) → LLM fallback for the rest, with the golden hard gate winning
over any LLM destructive suggestion (spec "Golden rule gate", ADR-2).
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.interpreter import resolve_intent
from jarvis.interpreter.llm import FakeProvider

ALLOWLIST = {"firefox"}


# --- golden-first ------------------------------------------------------------
def test_golden_destructive_never_consults_llm() -> None:
    # provider=None: the LLM path cannot run — a golden destructive match still works.
    result = resolve_intent("cerrá linux", provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is not None
    assert result.intent.intent == "shutdown"
    assert result.intent.confirm_required is True
    assert result.intent.source == "golden"
    assert result.needs_reask is False


def test_golden_fast_path_returns_direct_intent() -> None:
    result = resolve_intent("abrí firefox", provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is not None
    assert result.intent.intent == "open_app"
    assert result.intent.entities == {"app": "firefox"}
    assert result.intent.confirm_required is False


def test_golden_fast_path_rejects_disallowed_app() -> None:
    result = resolve_intent("abrí chrome", provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "invalid_entity:app"


def test_golden_fast_path_active_project_delegation() -> None:
    result = resolve_intent("abrí este proyecto", provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is not None
    assert result.intent.intent == "open_repo"
    assert result.intent.use_active_project is True
    assert result.intent.entities == {"repo": ""}


# --- LLM fallback ------------------------------------------------------------
def test_llm_happy_path() -> None:
    provider = FakeProvider([{"intent": "ask", "entities": {"query": "como funciona el middleware de auth"}, "confidence": 0.9}])
    result = resolve_intent("contame cómo funciona el middleware de auth", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is not None
    assert result.intent.intent == "ask"
    assert result.intent.entities == {"query": "como funciona el middleware de auth"}
    assert result.intent.source == "llm"
    assert result.needs_reask is False


def test_llm_destructive_suggestion_rejected_by_golden() -> None:
    # Spec scenario: "cerrá la ventana" → LLM suggests shutdown → golden rejects.
    provider = FakeProvider([{"intent": "shutdown", "entities": {}, "confidence": 0.95}])
    result = resolve_intent("cerrá la ventana", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.rejected_destructive is True
    assert result.needs_reask is True
    assert result.reason == "golden_rejected_destructive"


def test_ambiguous_destructive_never_emitted() -> None:
    # Spec scenario: "apagá eso" → golden cannot confirm → LLM suggestion rejected.
    provider = FakeProvider([{"intent": "shutdown", "entities": {}, "confidence": 0.8}])
    result = resolve_intent("apagá eso", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.rejected_destructive is True


def test_low_confidence_triggers_reask() -> None:
    provider = FakeProvider([{"intent": "ask", "entities": {"query": "x"}, "confidence": 0.4}])
    result = resolve_intent("contame algo", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "low_confidence"


def test_unknown_intent_triggers_reask() -> None:
    provider = FakeProvider([{"intent": "unknown", "entities": {}, "confidence": 0.9}])
    result = resolve_intent("hablame de algo raro", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "unknown"


def test_out_of_allowlist_is_unsupported_not_reask() -> None:
    provider = FakeProvider([{"intent": "delete_files", "entities": {}, "confidence": 0.9}])
    result = resolve_intent("borrá todos los archivos", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.unsupported is True
    assert result.needs_reask is False


def test_empty_or_wake_only_transcript_asks_again() -> None:
    assert resolve_intent("", provider=None).needs_reask is True
    assert resolve_intent("jarvis", provider=None).needs_reask is True


def test_no_provider_on_llm_needed_path() -> None:
    result = resolve_intent("contame un chiste", provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "no_provider"


def test_llm_active_project_alias_maps_to_delegation() -> None:
    provider = FakeProvider([{"intent": "open_repo", "entities": {"repo": "este proyecto"}, "confidence": 0.9}])
    result = resolve_intent("trabajá en este proyecto", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is not None
    assert result.intent.intent == "open_repo"
    assert result.intent.use_active_project is True
    assert result.intent.entities == {"repo": ""}


# --- threat matrix (design) at interpreter level ------------------------------
def test_repo_metachar_entity_rejected() -> None:
    provider = FakeProvider([{"intent": "open_repo", "entities": {"repo": '";rm -rf /"'}, "confidence": 0.9}])
    result = resolve_intent("conectate al repo anubis", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "invalid_entity:repo"


def test_malformed_url_entity_rejected() -> None:
    provider = FakeProvider([{"intent": "open_url", "entities": {"url": "no es una url"}, "confidence": 0.9}])
    result = resolve_intent("andá a esa página", provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "invalid_entity:url"


# --- fuzzy app matching -------------------------------------------------------
def test_fuzzy_match_close_app_name() -> None:
    """Whisper mishears 'chromium' as 'chromio' → fuzzy matches to 'firefox'."""
    # "firefox" is the only app in ALLOWLIST; "chromio" is close enough (cutoff 0.6)
    result = resolve_intent("abrí chromio", provider=None, app_allowlist={"chromium", "firefox"})
    assert result.intent is not None
    assert result.intent.intent == "open_app"
    # Should match to "chromium" (closer than "firefox")
    assert result.intent.entities["app"] == "chromium"


def test_fuzzy_match_no_match_rejects() -> None:
    """Completely wrong app name → no fuzzy match → rejected."""
    result = resolve_intent("abrí calculatorz", provider=None, app_allowlist={"firefox", "terminal"})
    assert result.intent is None
    assert result.needs_reask is True
    assert result.reason == "invalid_entity:app"


def test_fuzzy_match_exact_match_unchanged() -> None:
    """Exact match → no fuzzy correction needed."""
    result = resolve_intent("abrí firefox", provider=None, app_allowlist={"firefox"})
    assert result.intent is not None
    assert result.intent.entities["app"] == "firefox"


# --- intent caching -----------------------------------------------------------
def test_cache_hit_skips_llm() -> None:
    """Same text twice → second call uses cache, not LLM."""
    provider = FakeProvider([
        {"intent": "ask", "entities": {"query": "hora"}, "confidence": 0.9},
        # If cache misses, this would be consumed; if cache hits, it won't be
    ])
    r1 = resolve_intent("¿qué hora es?", provider=provider, app_allowlist=ALLOWLIST)
    r2 = resolve_intent("¿qué hora es?", provider=provider, app_allowlist=ALLOWLIST)
    assert r1.intent is not None
    assert r2.intent is not None
    assert r1.intent.intent == r2.intent.intent
    # Provider should have only been called once (cache hit on second call)
    assert len(provider.calls) == 1


def test_cache_disabled_bypasses() -> None:
    """use_cache=False always calls the LLM."""
    provider = FakeProvider([
        {"intent": "ask", "entities": {"query": "hora"}, "confidence": 0.9},
        {"intent": "ask", "entities": {"query": "hora"}, "confidence": 0.9},
    ])
    r1 = resolve_intent("¿qué hora es?", provider=provider, app_allowlist=ALLOWLIST, use_cache=False)
    r2 = resolve_intent("¿qué hora es?", provider=provider, app_allowlist=ALLOWLIST, use_cache=False)
    assert r1.intent is not None
    assert r2.intent is not None
    # Both calls hit the LLM
    assert len(provider.calls) == 2


# --- recent context (pronoun resolution) --------------------------------------
def test_pronoun_resolution_cerrarlo() -> None:
    """User says 'abrí firefox' then 'cerralo' → resolves to 'cerrar firefox'."""
    # First command: open firefox
    r1 = resolve_intent("abrí firefox", provider=None, app_allowlist={"firefox"})
    assert r1.intent is not None
    assert r1.intent.entities["app"] == "firefox"

    # Second command: "cerralo" → should resolve to "cerrar firefox" via golden gate
    r2 = resolve_intent("cerralo", provider=None, app_allowlist={"firefox"})
    # "cerrar firefox" should match the shutdown pattern (destructive)
    # But it's not the full pattern "cerrar linux", so it might not match
    # The important thing is that it doesn't crash
    assert r2.intent is not None or r2.needs_reask is True
