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


def _g_natural(raw: str):
    """Gate over the NATURAL surface (canonicalize=False) — the interpreter's contract."""
    return gate(normalize(raw, canonicalize=False))


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
    ("revisá el pr actual", "review_pr", {"text": "actual"}),
    ("arreglá los warnings de ruff", "fix_warnings", {"text": "de ruff"}),
    ("recordame sacar la ropa en 10 minutos", "set_reminder", {"text": "sacar la ropa en 10 minutos"}),
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


# --- free-text entities stay natural (WARNING #1 fix) ------------------------
def test_free_text_query_keeps_original_verbs() -> None:
    # "se crea" must NOT become "se crear": the surface is natural, only the
    # golden patterns carry the rioplatense variants.
    intent = _g_natural("preguntale a opencode cómo se crea una tabla")
    assert intent is not None
    assert intent.intent == "ask"
    assert intent.entities["query"] == "como se crea una tabla"


def test_web_search_query_keeps_original_verbs() -> None:
    intent = _g_natural("buscá cómo se arma un esquema de base de datos")
    assert intent is not None
    assert intent.intent == "web_search"
    assert intent.entities["query"] == "como se arma un esquema de base de datos"


def test_ask_query_with_verb_inside_entity() -> None:
    intent = _g_natural("preguntale cómo se configura el agente")
    assert intent is not None
    assert intent.intent == "ask"
    assert intent.entities["query"] == "como se configura el agente"


# --- golden gate expansion: common git/dev commands ---------------------------
def test_git_status_fast_path() -> None:
    intent = _g("mostrá el estado")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "git status"}


def test_git_status_variant() -> None:
    intent = _g("mirá el estado")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "git status"}


def test_git_commit_with_message() -> None:
    intent = _g('creá un commit fix login')
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": 'git commit -m "fix login"'}


def test_git_commit_no_message() -> None:
    intent = _g("creá un commit")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "git commit"}


def test_git_push_fast_path() -> None:
    intent = _g("subí los cambios")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "git push"}


def test_make_clean_fast_path() -> None:
    intent = _g("limpiá")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "make clean"}


def test_make_build_fast_path() -> None:
    intent = _g("compilá")
    assert intent is not None
    assert intent.intent == "execute"
    assert intent.entities == {"command": "make build"}


# --- T-SAFE-01: expanded destructive set (hardline blocklist) ----------------
EXPANDED_DESTRUCTIVE_CASES: list[tuple[str, str, bool]] = [
    # (raw utterance, expected intent, policy-blocked flag)
    ("formateá el disco", "format_disk", True),
    ("formatear el disco", "format_disk", True),
    ("formateá el hdd", "format_disk", True),
    ("formateá el ssd", "format_disk", True),
    ("formateá la memoria", "format_disk", True),
    ("borrá el sistema", "wipe_system", True),
    ("borrar el disco por completo", "wipe_system", True),
    ("destruí la partición entera", "wipe_system", True),
    ("borrá el sistema ya", "wipe_system", True),
    ("eliminá todo en el disco", "delete_all", True),
    ("borrá todo lo que haya en el disco", "delete_all", True),
    ("borrá todos mis archivos", "delete_all", True),
    ("borrá todo", "delete_all", True),
    ("matá un proceso", "kill_process", True),
    ("matar el proceso", "kill_process", True),
    ("eliminá ese proceso", "kill_process", True),
    ("cortá un proceso", "kill_process", True),
]


@pytest.mark.parametrize(("raw", "expected", "blocked"), EXPANDED_DESTRUCTIVE_CASES)
def test_expanded_destructive_gate_emits_with_confirm_and_blocked(
    raw: str, expected: str, blocked: bool
) -> None:
    intent = _g(raw)
    assert intent is not None
    assert intent.intent == expected
    assert intent.confirm_required is True
    assert intent.confidence == 1.0
    assert intent.source == "golden"
    assert intent.blocked is blocked


def test_operator_destructives_are_not_policy_blocked() -> None:
    # shutdown/reboot/power_off_self have real operators: recognized but NOT
    # policy-blocked (the confirm gate guards them, not a denial handler).
    for raw in ("cerrá linux", "reiniciá la máquina", "apagate"):
        intent = _g(raw)
        assert intent is not None
        assert intent.blocked is False


NON_DESTRUCTIVE_CONTAINING_BORRAR: list[str] = [
    "borrar un archivo",           # single file → not delete_all/wipe_system
    "borrar el historial",         # no disk/system target
    "borrar la cache de firefox",
    "eliminar un comentario",
    "destruir el cache",
    "matar el tiempo",             # idiom, not a process
    "cortar la luz",               # not a process
    "formatear un documento",      # not a disk target
    "borrar el disco de la bici",  # "el disco" + trailing words → full anchor
]


@pytest.mark.parametrize("raw", NON_DESTRUCTIVE_CONTAINING_BORRAR)
def test_non_destructive_borrar_phrases_never_match_destructive(raw: str) -> None:
    # Full-string anchoring must keep "borrar X" out of the destructive gate
    # unless the whole utterance is a destructive target.
    assert _g(raw) is None


@pytest.mark.parametrize("raw", [
    "cómo está el clima", "qué clima hace", "cuál es el pronóstico de hoy",
    "cómo está el clima en Córdoba", "cuál es la temperatura",
    "qué temperatura hace", "qué temperatura hay", "qué temperatura hay en Córdoba",
    "qué temperatura hace en San Francisco Estados Unidos", "qué temperatura hay en una localidad",
])
def test_weather_is_a_narrow_golden_fast_path(raw: str) -> None:
    intent = _g(raw)
    assert intent is not None
    assert intent.intent == "general_qa"
    assert intent.entities["weather_location"] in (
        "", "cordoba", "san francisco estados unidos", "una localidad"
    )
    assert intent.entities["weather_ambiguous"] == "false"
    assert intent.source == "golden"


def test_weather_missing_location_is_explicitly_ambiguous() -> None:
    intent = _g("qué clima hace en")
    assert intent is not None
    assert intent.entities["weather_ambiguous"] == "true"


def test_weather_accepts_explicit_multiword_locations() -> None:
    for raw, location in (
        ("qué temperatura hay en Córdoba", "cordoba"),
        ("qué temperatura hace en San Francisco Estados Unidos", "san francisco estados unidos"),
        ("qué temperatura hay en una localidad", "una localidad"),
    ):
        intent = _g(raw)
        assert intent is not None
        assert intent.entities["weather_location"] == location
        assert intent.entities["weather_ambiguous"] == "false"


def test_weather_rejects_command_like_or_trailing_text() -> None:
    for raw in (
        "qué temperatura hay en Córdoba y abrí firefox",
        "qué temperatura hace en Córdoba por favor",
        "qué temperatura hay en Córdoba ejecuta el comando",
    ):
        assert _g(raw) is None


@pytest.mark.parametrize("raw", [
    "qué hora es", "decime la hora", "qué fecha es", "qué fecha es hoy",
    "qué día es hoy", "qué día de la semana es",
])
def test_local_datetime_questions_are_exact_golden_fast_paths(raw: str) -> None:
    intent = _g(raw)
    assert intent is not None
    assert intent.intent == "general_qa"
    assert intent.source == "golden"
    assert intent.entities["local_answer"] in {"time", "date", "weekday"}


@pytest.mark.parametrize("raw", [
    "qué hora es ahora", "decime la hora por favor", "qué fecha fue ayer",
    "qué día será mañana", "qué día de la semana es hoy",
])
def test_extended_local_datetime_questions_fall_through(raw: str) -> None:
    assert _g(raw) is None


def test_unrecognized_weather_text_stays_unmatched() -> None:
    assert _g("decime si mañana llueve") is None
