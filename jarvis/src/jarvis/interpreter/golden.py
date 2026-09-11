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
    (
        "format_disk",
        re.compile(
            rf"^(?:{_verb_alt('formatear')}) "
            rf"(?:el disco|el hdd|el ssd|la memoria)"
            rf"(?: ya| ahora)?$"
        ),
    ),
    (
        "wipe_system",
        re.compile(
            rf"^(?:{_verb_alt('borrar')}|{_verb_alt('destruir')}) "
            rf"(?:el sistema|el disco|la particion)"
            rf"(?: por completo| entera| entero)?(?: ya| ahora)?$"
        ),
    ),
    (
        "delete_all",
        re.compile(
            rf"^(?:{_verb_alt('borrar')}|{_verb_alt('eliminar')}) "
            rf"(?:todo(?: lo que haya)? en el disco|todos mis archivos|todo)"
            rf"(?: ya| ahora)?$"
        ),
    ),
    (
        "kill_process",
        re.compile(
            rf"^(?:{_verb_alt('matar')}|{_verb_alt('eliminar')}|{_verb_alt('cortar')}) "
            rf"(?:un |el |ese |este )?proceso(?: ya| ahora)?$"
        ),
    ),
)

# Policy-blocked destructive intents: recognized by the gate, but there is no
# real operator behind them — the registry handler (blocked_destructive)
# rejects them with a spoken denial (T-SAFE-01, Layer 1 hardline blocklist).
POLICY_BLOCKED_INTENTS: frozenset[str] = frozenset({
    "format_disk", "wipe_system", "delete_all", "kill_process",
})

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
_REVIEW_PR = re.compile(rf"^{_verb_alt('revisar')} (?:el |la )?(?:pr|pull request)(?: (.*))?$")
_FIX_WARNINGS = re.compile(r"^(?:arregla|corregi|corregir|fixea|fixear) (?:los |las )?(?:warnings|advertencias)(?: (.*))?$")
_HELP = re.compile(rf"^(?:{_verb_alt('ayudar')}|que podes hacer|que sabes hacer|que puede hacer)$")
_REMINDER = re.compile(r"^(?:recordame|recuerdame|recordar) (.+)$")
# Deliberately narrow local date/time vocabulary: exact normalized forms only.
_LOCAL_TIME = re.compile(r"^(que hora es|decime la hora)$")
_LOCAL_DATE = re.compile(r"^(que fecha es|que fecha es hoy)$")
_LOCAL_WEEKDAY = re.compile(r"^(que dia es hoy|que dia de la semana es)$")

def _local_answer_kind(kind: str) -> Callable[[re.Match[str]], dict[str, str]]:
    return lambda m: {"query": m.group(0), "local_answer": kind}

# Deliberately narrow weather vocabulary: no broad question/command parsing.
_WEATHER = re.compile(
    r"^(?:como esta el clima|que clima hace|cual es el pronostico de hoy|"
    r"cual es la temperatura|que temperatura hace|que temperatura hay)"
    r"(?: en(?: ([a-z0-9][a-z0-9._-]*(?: [a-z0-9][a-z0-9._-]*){0,11}))?)?$"
)
# Keep locations flexible for normal locality/city/country names while
# rejecting command-like or sentence-like trailing text.
_WEATHER_LOCATION_REJECTS = frozenset({
    "ahora", "ayer", "decime", "dame", "despues", "ejecuta", "ejecutar",
    "hoy", "manana", "muestra", "mostrar", "por", "favor", "que", "y",
    "abrir", "abri", "busca", "buscar", "cierra", "cerrar", "crea", "crear",
    "elimina", "eliminar", "hace", "hay", "necesito", "podes", "puedes",
})
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

# Exact Spotify controls and bounded catalog clarification forms.
_SPOTIFY_PLAY = re.compile(r"^(?:reproducir|reproduci) spotify$")
_SPOTIFY_PAUSE = re.compile(r"^(?:pausar|pausa) spotify$")
_SPOTIFY_SEARCH = re.compile(
    r"^(?:buscar|busca) (?:el |la )?(album|artista|artistas) (.+)$"
)
_SPOTIFY_SELECTION = re.compile(
    r"^(?:reproducir|reproduci|elegir|elegi|seleccionar|selecciona) "
    r"(?:(?:el |la )?(primero|primera|segundo|segunda|tercero|tercera|cuarto|cuarta|quinto|quinta)|seleccion (?:id )?([A-Za-z0-9_-]{8,32}))$"
)


def _repo_from_match(m: re.Match[str]) -> dict[str, str]:
    # Empty repo means "the active project" (delegated to orchestrator, PR3).
    return {"repo": m.group(1).strip() if m.group(1) else ""}


def _web_search_from_match(m: re.Match[str]) -> dict[str, str]:
    return {"query": m.group(1).strip(), "engine": "google"}


def _spotify_search_from_match(m: re.Match[str]) -> dict[str, str]:
    kind = "album" if m.group(1) == "album" else "artist"
    return {"kind": kind, "query": m.group(2).strip()}


def _spotify_selection_from_match(m: re.Match[str]) -> dict[str, str]:
    ordinal = {
        "primero": "1", "primera": "1", "segundo": "2", "segunda": "2",
        "tercero": "3", "tercera": "3", "cuarto": "4", "cuarta": "4",
        "quinto": "5", "quinta": "5",
    }
    return {"selection_id": ordinal.get(m.group(1), m.group(2))}


def _optional_text(default: str) -> Callable[[re.Match[str]], dict[str, str]]:
    def extract(m: re.Match[str]) -> dict[str, str]:
        value = m.group(1).strip() if m.group(1) else default
        return {"text": value}
    return extract


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


def _weather_location_allowed(location: str | None) -> bool:
    if not location:
        return True
    return not _WEATHER_LOCATION_REJECTS.intersection(location.split())


def _weather_extract(m: re.Match[str]) -> dict[str, str]:
    location = (m.group(1) or "").strip()
    return {
        "query": m.group(0),
        "weather_location": location,
        "weather_ambiguous": "true" if m.group(0).endswith(" en") else "false",
    }


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
    (_SPOTIFY_PLAY, "spotify_play", lambda m: {}),
    (_SPOTIFY_PAUSE, "spotify_pause", lambda m: {}),
    (_SPOTIFY_SEARCH, "spotify_search", _spotify_search_from_match),
    (_SPOTIFY_SELECTION, "spotify_play_selection", _spotify_selection_from_match),
    (_OPEN_APP, "open_app", _single_group("app")),
    (_WEB_SEARCH, "web_search", _web_search_from_match),
    (_ASK, "ask", _single_group("query")),
    (_REVIEW_PR, "review_pr", _optional_text("actual")),
    (_FIX_WARNINGS, "fix_warnings", _optional_text("todos")),
    (_REMINDER, "set_reminder", _single_group("text")),
    (_LOCAL_TIME, "general_qa", _local_answer_kind("time")),
    (_LOCAL_DATE, "general_qa", _local_answer_kind("date")),
    (_LOCAL_WEEKDAY, "general_qa", _local_answer_kind("weekday")),
    (_WEATHER, "general_qa", _weather_extract),
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
                blocked=intent in POLICY_BLOCKED_INTENTS,
                source="golden",
            )
    for pattern, intent, extract in FAST_PATH_PATTERNS:
        match = pattern.match(normalized)
        if match:
            if pattern is _WEATHER and not _weather_location_allowed(match.group(1)):
                continue
            return Intent(
                intent=intent,
                entities=extract(match),
                confidence=0.9,
                confirm_required=False,
                source="golden",
            )
    return None
