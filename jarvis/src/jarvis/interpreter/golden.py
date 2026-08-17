"""Deterministic golden gate (PR2, tasks 2.1/2.3).

Runs FIRST, before the LLM (ADR-2): the destructive patterns are the hard gate
— a match emits the destructive intent with ``confirm_required=True`` and the
LLM is NEVER consulted (spec: "never depends on the LLM"). Canonical
non-destructive fast-path patterns return a direct intent (latency win, design
open question resolved in this slice). No match → ``gate`` returns ``None`` and
the interpreter delegates to the LLM — and any destructive intent the LLM
suggests without a golden match is rejected upstream.

Anchoring rules:
- Destructive patterns are full-string anchored (``^...$``) for safety:
  "apagar la luz" must NOT trigger shutdown.
- Non-destructive patterns are prefix-anchored (``^...``) only, allowing
  trailing text: "abrir el proyecto y limpiar" matches open_repo, and
  entity validation catches bad extractions downstream.
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
# Prefix-anchored (^...) only — trailing text is allowed. Entity validation
# downstream catches bad extractions (e.g. "abrir el repo; rm -rf /").
_OPEN_REPO_PROJECT = re.compile(
    rf"^{_verb_alt('abrir')} (?:el |la |este |mi |nuestro |ese )?(?:proyecto|repo|repositorio)(?: (.*))?$"
)
_OPEN_REPO_OPENCODE = re.compile(
    rf"^{_verb_alt('abrir')} opencode(?: en el (?:repo|repositorio|proyecto))?(?: (.*))?$"
)
_OPEN_REPO_POINTER = re.compile(rf"^{_verb_alt('abrir')} (?:el |la )?(?:este|aca|aqui)$")
_OPEN_APP = re.compile(rf"^{_verb_alt('abrir')} (.+)$")
_WEB_SEARCH = re.compile(rf"^{_verb_alt('buscar')} (.+)$")
_ASK = re.compile(rf"^{_verb_alt('preguntar')}(?: a opencode)? (.+)$")
_HELP = re.compile(rf"^(?:{_verb_alt('ayudar')}|que podes hacer|que sabes hacer|que puede hacer)$")

# Create-doc patterns: common verbs that map to create_doc intent.
# These extract free-text content (the LLM generates the document, not a shell cmd).
# The noun (documento/doc/archivo/nota/txt) must be present to avoid matching
# "crear un script" which should go to the LLM for execute intent.
_CREATE_DOC = re.compile(
    rf"^{_verb_alt('crear')} (?:un |una |el |la )?(?:documento|doc|archivo|nota|txt)(?: (.*))?$"
)
_CREATE_DOC_WRITE = re.compile(
    rf"^{_verb_alt('escribir')} (?:un |una |el |la )?(?:documento|doc|archivo|nota|txt)(?: (.*))?$"
)

# --- common git/dev commands (fast-path to avoid LLM) -----------------------
# These are common enough to warrant golden patterns; saves ~1-5s per call.
_GIT_STATUS = re.compile(
    rf"^(?:{_verb_alt('mostrar')} (?:el )?estado|{_verb_alt('mirar')} (?:el )?estado"
    rf"|{_verb_alt('chequear')} (?:el )?estado)$"
)
_GIT_COMMIT = re.compile(
    rf"^{_verb_alt('crear')} (?:un )?(?:commit|commitear)(?: (.*))?$"
)
_GIT_PUSH = re.compile(
    rf"^{_verb_alt('subir')} (?:los )?(?:cambios|commits|el código)(?: (.*))?$"
)
_MAKE_CLEAN = re.compile(
    rf"^{_verb_alt('limpiar')}(?: (?:todo|el proyecto|build))?$"
)
_MAKE_BUILD = re.compile(
    rf"^{_verb_alt('compilar')}(?: (?:el proyecto|todo))?$"
)


def _repo_from_match(m: re.Match[str]) -> dict[str, str]:
    # Empty repo means "the active project" (delegated to orchestrator, PR3).
    return {"repo": m.group(1).strip() if m.group(1) else ""}


def _web_search_from_match(m: re.Match[str]) -> dict[str, str]:
    return {"query": m.group(1).strip(), "engine": "google"}


def _single_group(key: str) -> Callable[[re.Match[str]], dict[str, str]]:
    def extract(m: re.Match[str]) -> dict[str, str]:
        return {key: m.group(1).strip()}
    return extract


def _git_status_extract(m: re.Match[str]) -> dict[str, str]:
    return {"command": "git status"}


def _git_commit_extract(m: re.Match[str]) -> dict[str, str]:
    msg = m.group(1).strip() if m.group(1) else ""
    if msg:
        return {"command": f'git commit -m "{msg}"'}
    return {"command": "git commit"}


def _git_push_extract(m: re.Match[str]) -> dict[str, str]:
    return {"command": "git push"}


def _make_clean_extract(m: re.Match[str]) -> dict[str, str]:
    return {"command": "make clean"}


def _make_build_extract(m: re.Match[str]) -> dict[str, str]:
    return {"command": "make build"}


# (pattern, intent, entity extractor) — first match wins; repo patterns must
# precede open_app so "abrir el repo X" never falls into the app fast path.
FAST_PATH_PATTERNS: tuple[tuple[re.Pattern[str], str, Callable[[re.Match[str]], dict[str, str]]], ...] = (
    (_OPEN_REPO_PROJECT, "open_repo", _repo_from_match),
    (_OPEN_REPO_OPENCODE, "open_repo", _repo_from_match),
    (_OPEN_REPO_POINTER, "open_repo", lambda m: {"repo": ""}),
    (_CREATE_DOC, "create_doc", _single_group("text")),
    (_CREATE_DOC_WRITE, "create_doc", _single_group("text")),
    (_GIT_STATUS, "execute", _git_status_extract),
    (_GIT_COMMIT, "execute", _git_commit_extract),
    (_GIT_PUSH, "execute", _git_push_extract),
    (_MAKE_CLEAN, "execute", _make_clean_extract),
    (_MAKE_BUILD, "execute", _make_build_extract),
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
