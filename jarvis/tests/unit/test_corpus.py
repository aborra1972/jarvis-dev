"""Corpus replay tests (PR2, task 2.5): M1/M3 orders from the PRD + threat matrix.

Deterministic replay of the PRD 3.2 order table and the spec scenarios through
the full interpreter (normalize → golden → LLM fallback with fake provider).
M1 proxy: every corpus order must resolve to the right intent+entities. M3
proxy: STT variance is simulated by rioplatense variant rows resolving
identically.
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.interpreter import resolve_intent
from jarvis.interpreter.llm import FakeProvider

ALLOWLIST = {"firefox"}

# Golden-path corpus: canonical/rioplatense orders resolved WITHOUT the LLM.
GOLDEN_CORPUS: list[dict] = [
    # PRD 3.2: work session / research / system / web rows
    {"raw": "abrí el proyecto jarvis", "intent": "open_repo", "entities": {"repo": "jarvis"}},
    {"raw": "abrime el repo anubis-api", "intent": "open_repo", "entities": {"repo": "anubis-api"}},
    {"raw": "abrí opencode en el repo anubis-api", "intent": "open_repo", "entities": {"repo": "anubis-api"}},
    {"raw": "abrí firefox", "intent": "open_app", "entities": {"app": "firefox"}},
    {"raw": "buscá en internet qué es tal librería", "intent": "web_search",
     "entities": {"query": "en internet que es tal libreria", "engine": "google"}},
    {"raw": "preguntale cómo funciona el middleware de auth", "intent": "ask",
     "entities": {"query": "como funciona el middleware de auth"}},
    {"raw": "preguntale a opencode cómo se usa pytest", "intent": "ask",
     "entities": {"query": "como se usa pytest"}},
    # destructive golden gate (spec: golden table confirms → confirm gate)
    {"raw": "cerrá linux", "intent": "shutdown", "confirm": True},
    {"raw": "cerra linux", "intent": "shutdown", "confirm": True},
    {"raw": "cerrame linux", "intent": "shutdown", "confirm": True},
    {"raw": "reiniciá la máquina", "intent": "reboot", "confirm": True},
    {"raw": "jarvis, apagate", "intent": "power_off_self", "confirm": True},
    {"raw": "apagame", "intent": "power_off_self", "confirm": True},
    {"raw": "dormite ahora", "intent": "power_off_self", "confirm": True},
    # active-project delegation (orchestrator PR3 fills the repo)
    {"raw": "abrí este proyecto", "intent": "open_repo", "active": True},
    {"raw": "¿podés abrir el repo?", "intent": "open_repo", "active": True},
    # help
    {"raw": "ayuda", "intent": "help"},
    {"raw": "que podes hacer", "intent": "help"},
    # create_doc golden fast path
    {"raw": "creá un documento con el resumen del sprint", "intent": "create_doc",
     "entities": {"text": "con el resumen del sprint"}},
]


@pytest.mark.parametrize("row", GOLDEN_CORPUS, ids=[r["raw"] for r in GOLDEN_CORPUS])
def test_golden_corpus_replay(row: dict) -> None:
    result = resolve_intent(row["raw"], provider=None, app_allowlist=ALLOWLIST)
    assert result.intent is not None, f"{row['raw']!r} should resolve via golden"
    assert result.intent.intent == row["intent"]
    assert result.intent.source == "golden"
    assert result.needs_reask is False
    if "entities" in row:
        assert result.intent.entities == row["entities"]
    if row.get("confirm"):
        assert result.intent.confirm_required is True
    else:
        assert result.intent.confirm_required is False
    if row.get("active"):
        assert result.intent.use_active_project is True


# LLM-path corpus: PRD 3.2 rows resolved through the fake provider.
LLM_CORPUS: list[dict] = [
    {"raw": "setealo en modo SDD con artifacts en engram", "intent": "configure",
     "payload": {"intent": "configure", "entities": {"text": "en modo sdd con artifacts en engram"}, "confidence": 0.9}},
    {"raw": "ayudame a armar un PRD para un jarvis de voz", "intent": "create_artifact",
     "payload": {"intent": "create_artifact", "entities": {"text": "a armar un prd para un jarvis de voz"}, "confidence": 0.9}},
    {"raw": "pedile que implemente la migración 076 con TDD", "intent": "implement",
     "payload": {"intent": "implement", "entities": {"text": "que implemente la migracion 076 con tdd"}, "confidence": 0.9}},
    {"raw": "que revise el último commit y me diga los riesgos", "intent": "review",
     "payload": {"intent": "review", "entities": {"text": "que revise el ultimo commit y me diga los riesgos"}, "confidence": 0.9}},
]


@pytest.mark.parametrize("row", LLM_CORPUS, ids=[r["raw"] for r in LLM_CORPUS])
def test_llm_corpus_replay(row: dict) -> None:
    provider = FakeProvider([row["payload"]])
    result = resolve_intent(row["raw"], provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is not None, f"{row['raw']!r} should resolve via LLM"
    assert result.intent.intent == row["intent"]
    assert result.intent.source == "llm"
    assert result.intent.entities == row["payload"]["entities"]
    assert result.needs_reask is False


# Threat matrix (design + spec): nothing destructive/unsafe is ever emitted.
THREAT_CASES: list[dict] = [
    # spec: LLM misinterpretation rejected ("cerrá la ventana" → shutdown rejected)
    {"raw": "cerrá la ventana", "payload": {"intent": "shutdown", "entities": {}, "confidence": 0.95},
     "flag": "rejected_destructive"},
    # spec: ambiguous destructive utterance → re-ask, never emitted
    {"raw": "apagá eso", "payload": {"intent": "shutdown", "entities": {}, "confidence": 0.8},
     "flag": "rejected_destructive"},
    # allowlist: destructive out-of-scope request → not supported
    {"raw": "borrá todos los archivos", "payload": {"intent": "delete_files", "entities": {}, "confidence": 0.9},
     "flag": "unsupported"},
    # threat matrix: repo metachar injection (";rm -rf /") → rejected
    {"raw": "conectate al repo anubis", "payload": {"intent": "open_repo", "entities": {"repo": '";rm -rf /"'}, "confidence": 0.9},
     "flag": "invalid_entity:repo"},
    # threat matrix: disallowed app (golden fast path and LLM path)
    {"raw": "abrí chrome", "payload": None, "flag": "invalid_entity:app"},
    {"raw": "abrí chrome", "payload": {"intent": "open_app", "entities": {"app": "chrome"}, "confidence": 0.9},
     "flag": "invalid_entity:app"},
    # threat matrix: malformed URL → rejected, nothing spawned
    {"raw": "andá a esa página", "payload": {"intent": "open_url", "entities": {"url": "no es una url"}, "confidence": 0.9},
     "flag": "invalid_entity:url"},
]


@pytest.mark.parametrize("row", THREAT_CASES, ids=[f"{row['raw']}->{row['flag']}" for row in THREAT_CASES])
def test_threat_matrix_never_emits(row: dict) -> None:
    provider = FakeProvider([row["payload"]]) if row["payload"] is not None else None
    result = resolve_intent(row["raw"], provider=provider, app_allowlist=ALLOWLIST)
    assert result.intent is None, f"{row['raw']!r} must never emit an intent"
    if row["flag"] == "rejected_destructive":
        assert result.rejected_destructive is True
        assert result.needs_reask is True
    elif row["flag"] == "unsupported":
        assert result.unsupported is True
    else:
        assert result.needs_reask is True
        assert result.reason == row["flag"]
