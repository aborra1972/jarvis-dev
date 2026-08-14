"""Deterministic golden gate (PR2, tasks 2.1/2.3).

Runs FIRST, before the LLM (ADR-2): the destructive patterns are the hard gate
— a match emits the destructive intent with ``confirm_required=True`` and the
LLM is NEVER consulted (spec: "never depends on the LLM"). Canonical
non-destructive fast-path patterns return a direct intent (latency win, design
open question resolved in this slice). No match → ``gate`` returns ``None`` and
the interpreter delegates to the LLM — and any destructive intent the LLM
suggests without a golden match is rejected upstream.

All patterns are full-string anchored and match the NORMALIZED transcript
(canonical infinitive forms produced by normalize.py): minimal surface, no
trailing words, no shell.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from jarvis.interpreter.normalize import VARIANT_MAP
from jarvis.interpreter.schema import Intent


def _verb_alt(verb: str) -> str:
    """Alternation of every rioplatense variant for ``verb`` plus the canonical form.

    Built from VARIANT_MAP so the gate matches the NATURAL surface ("cerrame
    linux") and the canonical surface ("cerrar linux") with one pattern set;
    longest alternatives first so phrase-level entries ("podes abrir") win
    over word-level ones ("abrir").
    """
    variants = {src for src, dst in VARIANT_MAP.items() if dst == verb}
    variants.add(verb)
    alternatives = sorted(variants, key=len, reverse=True)
    return "(?:" + "|".join(re.escape(alt) for alt in alternatives) + ")"


# (intent, regex) — destructive hard gate, checked in order.
DESTRUCTIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "shutdown",
        re.compile(
            rf"^(?:{_verb_alt('cerrar')}|{_verb_alt('apagar')}) "
            rf"(?:linux|la maquina|el equipo|el sistema|la pc|la compu|la computadora)"
            rf"(?: ya| ahora)?$"
        ),
    ),
    (
        "reboot",
        re.compile(
            rf"^{_verb_alt('reiniciar')} "
            rf"(?:linux|la maquina|el equipo|el sistema|la pc|la compu|la computadora)"
            rf"(?: ya| ahora)?$"
        ),
    ),
    ("power_off_self", re.compile(rf"^(?:{_verb_alt('apagarse')}|{_verb_alt('dormirse')})(?: ya| ahora)?$")),
)

# --- canonical non-destructive fast-path patterns ---------------------------
_OPEN_REPO_PROJECT = re.compile(
    rf"^{_verb_alt('abrir')} (?:el |la |este |mi |nuestro |ese )?(?:proyecto|repo|repositorio)(?: (.+))?$"
)
_OPEN_REPO_OPENCODE = re.compile(
    rf"^{_verb_alt('abrir')} opencode(?: en el (?:repo|repositorio|proyecto))?(?: (.+))?$"
)
_OPEN_REPO_POINTER = re.compile(rf"^{_verb_alt('abrir')} (?:el |la )?(?:este|aca|aqui)$")
_OPEN_APP = re.compile(rf"^{_verb_alt('abrir')} (.+)$")
_WEB_SEARCH = re.compile(rf"^{_verb_alt('buscar')} (.+)$")
_ASK = re.compile(rf"^{_verb_alt('preguntar')}(?: a opencode)? (.+)$")
_HELP = re.compile(rf"^(?:{_verb_alt('ayudar')}|que podes hacer|que sabes hacer|que puede hacer)$")


def _repo_from_match(m: re.Match[str]) -> dict[str, str]:
    # Empty repo means "the active project" (delegated to orchestrator, PR3).
    return {"repo": m.group(1).strip() if m.group(1) else ""}


def _web_search_from_match(m: re.Match[str]) -> dict[str, str]:
    return {"query": m.group(1).strip(), "engine": "google"}


def _single_group(key: str) -> Callable[[re.Match[str]], dict[str, str]]:
    def extract(m: re.Match[str]) -> dict[str, str]:
        return {key: m.group(1).strip()}
    return extract


# (pattern, intent, entity extractor) — first match wins; repo patterns must
# precede open_app so "abrir el repo X" never falls into the app fast path.
FAST_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str, Callable[[re.Match[str]], dict[str, str]]], ...] = (
    (_OPEN_REPO_PROJECT, "open_repo", _repo_from_match),
    (_OPEN_REPO_OPENCODE, "open_repo", _repo_from_match),
    (_OPEN_REPO_POINTER, "open_repo", lambda m: {"repo": ""}),
    (_OPEN_APP, "open_app", _single_group("app")),
    (_WEB_SEARCH, "web_search", _web_search_from_match),
    (_ASK, "ask", _single_group("query")),
    (_HELP, "help", lambda m: {}),
)


def gate(normalized: str) -> Intent | None:
    """Match a normalized transcript; returns an Intent or None (delegate)."""
    if not normalized:
        return None
    for intent, pattern in DESTRUCTIVE_PATTERNS:
        if pattern.match(normalized):
            return Intent(
                intent=intent,
                entities={},
                confidence=1.0,
                confirm_required=True,
                source="golden",
            )
    for pattern, intent, extract in FAST_PATH_PATTERNS:
        match = pattern.match(normalized)
        if match:
            return Intent(
                intent=intent,
                entities=extract(match),
                confidence=0.9,
                confirm_required=False,
                source="golden",
            )
    return None
