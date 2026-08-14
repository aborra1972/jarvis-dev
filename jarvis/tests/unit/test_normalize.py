"""Table-driven tests for rioplatense normalization (PR2, task 2.2).

Covers the normalize pipeline contract (design "Interpreter (hybrid, safe)":
lowercase, accent strip, punctuation strip, wake-word strip, whitespace
collapse) plus the rioplatense voseo → canonical-infinitive table the golden
gate and the LLM prompt consume.
"""

from __future__ import annotations

import pytest

from jarvis.interpreter.normalize import normalize

CASES: list[tuple[str, str]] = [
    # --- basic pipeline ---
    ("Jarvis, abrí Firefox", "abrir firefox"),
    ("  jArVis   reiniciá   la   MÁQUINA  ", "reiniciar la maquina"),
    ("¿CÓMO estás?", "como estas"),
    ("¡Hola!", "hola"),
    ("", ""),
    ("jarvis", ""),
    ("jarvis, apagate", "apagarse"),
    # --- wake-word variants (design: strip leading wake-word token(s)) ---
    ("hey jarvis abrí el repo", "abrir el repo"),
    ("hola jarvis, cerrá linux", "cerrar linux"),
    ("ok jarvis abrí firefox", "abrir firefox"),
    ("oye jarvis abre el repo", "abrir el repo"),
    # --- rioplatense voseo/imperative → canonical infinitive ---
    ("cerrá linux", "cerrar linux"),
    ("cerra linux", "cerrar linux"),
    ("cerrame linux", "cerrar linux"),
    ("reiniciá la máquina", "reiniciar la maquina"),
    ("apagate ya", "apagarse ya"),
    ("apagame", "apagarse"),
    ("dormite ahora", "dormirse ahora"),
    ("abrí el proyecto jarvis", "abrir el proyecto jarvis"),
    ("abrime el repo anubis-api", "abrir el repo anubis-api"),
    ("buscá en internet qué es tal librería", "buscar en internet que es tal libreria"),
    ("preguntale a opencode cómo se usa pytest", "preguntar a opencode como se usa pytest"),
    ("preguntale cómo funciona el middleware de auth", "preguntar como funciona el middleware de auth"),
    ("¿podés abrir el repo?", "abrir el repo"),
    ("ayudame a armar un PRD", "ayudar a armar un prd"),
    ("borrá todos los archivos", "borrar todos los archivos"),
    ("pedile que implemente la migración 076 con TDD", "pedir que implemente la migracion 076 con tdd"),
    ("setealo en modo SDD con artifacts en engram", "setear en modo sdd con artifacts en engram"),
    ("creá un documento con el resumen del sprint", "crear un documento con el resumen del sprint"),
]


@pytest.mark.parametrize(("raw", "expected"), CASES)
def test_normalize_cases(raw: str, expected: str) -> None:
    assert normalize(raw) == expected
