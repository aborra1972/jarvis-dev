"""Golden gate tests (PR2, tasks 2.1/2.3).

The golden table is the AUTHORITATIVE gate for destructive intents (ADR-2,
spec "Golden rule gate"): regexes are full-string anchored, canonical forms.
It also carries the canonical non-destructive fast-path ("abrí X", "buscá X",
"preguntar X") that avoids LLM latency.
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.golden import gate
from jarvis.interpreter.normalize import normalize


def _g(raw: str):
    return gate(normalize(raw))


DESTRUCTIVE_CASES: list[tuple[str, str]] = [
    # (raw utterance, expected destructive intent)
    ("cerrá linux", "shutdown"),
    ("cerra linux", "shutdown"),
    ("cerrame linux", "shutdown"),
    ("apagá la máquina", "shutdown"),
    ("apagar el equipo", "shutdown"),
    ("cerrá el sistema", "shutdown"),
    ("apagá la pc", "shutdown"),
    ("apagá la compu", "shutdown"),
    ("cerrá linux ya", "shutdown"),
    ("reiniciá la máquina", "reboot"),
    ("reiniciar linux", "reboot"),
    ("reiniciar el sistema", "reboot"),
    ("reinicia la compu", "reboot"),
    ("jarvis, apagate", "power_off_self"),
    ("apagate ya", "power_off_self"),
    ("apagate ahora", "power_off_self"),
    ("apagame", "power_off_self"),
    ("dormite", "power_off_self"),
    ("dormite ahora", "power_off_self"),
]


@pytest.mark.parametrize(("raw", "expected"), DESTRUCTIVE_CASES)
def test_destructive_gate_emits_with_confirm(raw: str, expected: str) -> None:
    intent = _g(raw)
    assert intent is not None
    assert intent.intent == expected
    assert intent.confirm_required is True
    assert intent.confidence == 1.0
    assert intent.source == "golden"


NONE_CASES: list[str] = [
    "cerrar la ventana",          # spec: LLM misinterpretation rejected
    "apagar eso",                 # spec: ambiguous destructive utterance
    "apagar",                     # verb without a target
    "cerrar linux por favor",     # trailing words — full-string anchored
    "borrar todos los archivos",  # destructive but out of scope
    "abrir",                      # bare verb, no entity
    "buscar",
    "preguntar",
    "",
    "hola",
]


@pytest.mark.parametrize("raw", NONE_CASES)
def test_gate_returns_none(raw: str) -> None:
    assert _g(raw) is None


FAST_PATH_CASES: list[tuple[str, str, dict]] = [
    # (raw, expected intent, expected entities)
    ("abrí el proyecto jarvis", "open_repo", {"repo": "jarvis"}),
    ("abrime el repo anubis-api", "open_repo", {"repo": "anubis-api"}),
    ("abrir opencode en el repo anubis-api", "open_repo", {"repo": "anubis-api"}),
    ("abrí opencode", "open_repo", {"repo": ""}),        # active project delegation
    ("abrí este proyecto", "open_repo", {"repo": ""}),   # active project delegation
    ("abrí el proyecto", "open_repo", {"repo": ""}),     # active project delegation
    ("abrí este", "open_repo", {"repo": ""}),
    ("¿podés abrir el repo?", "open_repo", {"repo": ""}),
    ("abrí firefox", "open_app", {"app": "firefox"}),
    ("buscá en internet qué es tal librería", "web_search", {"query": "en internet que es tal libreria", "engine": "google"}),
    ("preguntale a opencode cómo se usa pytest", "ask", {"query": "como se usa pytest"}),
    ("preguntale cómo funciona el middleware de auth", "ask", {"query": "como funciona el middleware de auth"}),
    ("ayuda", "help", {}),
    ("que podes hacer", "help", {}),
]


@pytest.mark.parametrize(("raw", "expected_intent", "expected_entities"), FAST_PATH_CASES)
def test_fast_path_direct_intent(raw: str, expected_intent: str, expected_entities: dict) -> None:
    intent = _g(raw)
    assert intent is not None
    assert intent.intent == expected_intent
    assert intent.entities == expected_entities
    assert intent.confirm_required is False
    assert intent.confidence == 0.9
    assert intent.source == "golden"
