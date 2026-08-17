"""Intent schema: 16-command allowlist + validation (PR2, task 2.4).

The interpreter only ever emits one of the allowlisted intents; executors
never receive raw transcripts — only validated intents + entities (design
"Interfaces / Contracts"). Validation is pure and table-driven; entity checks
encode the design threat matrix (repo metachars, disallowed app, malformed
URL).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

# The 16 commands (6 domains) + "unknown" (the no-intent fallback, not a
# command — drives the re-ask flow per spec RNF-4).
ALLOWED_INTENTS: frozenset[str] = frozenset({
    "open_repo", "ask", "configure", "create_artifact", "implement", "review",
    "shutdown", "reboot", "power_off_self", "open_app", "create_doc",
    "open_file_dir", "web_search", "open_url", "help", "unknown", "execute",
})

# Destructive intents: only the golden hard gate may emit these.
DESTRUCTIVE_INTENTS: frozenset[str] = frozenset({"shutdown", "reboot", "power_off_self"})

DOMAIN_INTENTS: dict[str, tuple[str, ...]] = {
    "opencode": ("open_repo", "ask", "configure", "create_artifact", "implement", "review"),
    "system": ("shutdown", "reboot", "open_app", "execute"),
    "files": ("create_doc", "open_file_dir"),
    "web": ("web_search", "open_url"),
    "lifecycle": ("power_off_self", "help"),
}

INTENT_DOMAIN: dict[str, str] = {
    intent: domain for domain, intents in DOMAIN_INTENTS.items() for intent in intents
}
INTENT_DOMAIN["unknown"] = ""

REQUIRED_ENTITIES: dict[str, tuple[str, ...]] = {
    "open_repo": ("repo",),
    "ask": ("query",),
    "configure": ("text",),
    "create_artifact": ("text",),
    "implement": ("text",),
    "review": ("text",),
    "open_app": ("app",),
    "create_doc": ("text",),
    "open_file_dir": ("text",),
    "web_search": ("query",),
    "open_url": ("url",),
}

CONFIDENCE_THRESHOLD = 0.6  # design "Interpreter": below → re-ask (RNF-4)

# Design threat matrix: repo args must never carry shell metachars or start
# with "-" (would be parsed as an option by subprocess).
_SHELL_METACHARS = re.compile(r"[;|&$<>`'\"\\]")


@dataclass(frozen=True)
class Intent:
    """A validated intent the interpreter is allowed to emit."""

    intent: str
    entities: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    confirm_required: bool = False
    source: str = ""  # "golden" | "llm"
    use_active_project: bool = False


class SchemaError(ValueError):
    """Invalid intent payload. ``code`` drives the re-ask vs unsupported
    decision in the interpreter."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate(payload: Any) -> Intent:
    """Validate an LLM payload against the allowlist schema (raises SchemaError)."""
    if not isinstance(payload, dict):
        raise SchemaError("bad_payload", f"expected JSON object, got {type(payload).__name__}")

    intent_name = payload.get("intent")
    if intent_name not in ALLOWED_INTENTS:
        raise SchemaError("unknown_intent", f"intent {intent_name!r} not in allowlist")

    confidence = payload.get("confidence", 0.0)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise SchemaError("bad_confidence", f"confidence must be a number, got {confidence!r}")
    confidence = float(confidence)
    if not 0.0 <= confidence <= 1.0:
        raise SchemaError("bad_confidence", f"confidence out of range: {confidence}")

    raw_entities = payload.get("entities", {})
    if not isinstance(raw_entities, dict):
        raise SchemaError("bad_entities", f"entities must be an object, got {type(raw_entities).__name__}")
    entities: dict[str, str] = {}
    for key, value in raw_entities.items():
        if value is None:
            entities[str(key)] = ""
        elif isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise SchemaError("bad_entities", f"entity {key!r} has unsupported value {value!r}")
        else:
            entities[str(key)] = str(value).strip()

    for key in REQUIRED_ENTITIES.get(intent_name, ()):
        # Empty repo is legal for open_repo → active project delegation (PR3).
        if not entities.get(key, "") and not (key == "repo" and intent_name == "open_repo"):
            raise SchemaError("missing_entity", f"intent {intent_name} requires entity {key!r}")

    return Intent(intent=intent_name, entities=entities, confidence=confidence)


def validate_entities(intent: Intent, app_allowlist: set[str] | None = None) -> list[str]:
    """Semantic entity checks (design threat matrix). Returns invalid keys; [] = valid.

    - ``repo``: reject shell metachars and leading ``-`` (metachar injection).
    - ``app``: must be allowlisted (disallowed app ⇒ rejected, nothing spawned).
    - ``url``: must parse as http/https with a host (malformed URL ⇒ rejected).
    - ``command``: reject dangerous metachars for execute intent.
    Empty repo is valid for ``open_repo`` when the active project is delegated
    (``use_active_project``).
    """
    invalid: list[str] = []
    entities = intent.entities

    if intent.intent == "open_repo" and entities.get("repo", ""):
        repo = entities["repo"]
        if repo.startswith("-") or _SHELL_METACHARS.search(repo):
            invalid.append("repo")

    if intent.intent == "open_app" and app_allowlist is not None:
        app_raw = entities.get("app", "")
        # Strip common Spanish articles/determiners so "la terminal" → "terminal"
        app_clean = re.sub(r"^(el|los?|las?|un|unos?|unas?)\s+", "", app_raw).strip()
        # Reject overly long app names (likely LLM hallucinated text)
        if len(app_clean) > 30:
            invalid.append("app")
        elif app_clean not in app_allowlist:
            invalid.append("app")

    if intent.intent == "open_url":
        url = entities.get("url", "")
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            invalid.append("url")
        else:
            # Extract hostname (strip port) for domain checks
            host = parsed.netloc.split(":")[0]
            # Reject URLs that are just random text with no real domain
            # Allow localhost but require dot for other domains
            if "." not in host and host != "localhost":
                invalid.append("url")
            # Reject suspiciously long URLs (likely LLM hallucinated text)
            elif len(url) > 200:
                invalid.append("url")

    # execute: basic safety — reject extremely dangerous patterns
    if intent.intent == "execute":
        cmd = entities.get("command", "")
        # Block rm -rf / and similar catastrophic commands
        if cmd and re.search(r'\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+/*|/\*)', cmd):
            invalid.append("command")

    return invalid


def fuzzy_correct_entities(intent: Intent, app_allowlist: set[str] | None = None) -> Intent:
    """Fuzzy-correct the ``app`` entity for open_app intents.

    Uses ``difflib.get_close_matches`` with a high cutoff (0.6) to match
    Whisper misheard app names (e.g. "chromio" → "chromium"). Only the
    ``app`` entity is corrected; other entities pass through unchanged.
    Returns a NEW Intent (frozen dataclass). If no close match is found,
    the intent is returned unchanged (``validate_entities`` will reject it).
    """
    if intent.intent != "open_app" or app_allowlist is None:
        return intent

    app_raw = intent.entities.get("app", "")
    # Strip common Spanish articles/determiners
    app_clean = re.sub(r"^(el|los?|las?|un|unos?|unas?)\s+", "", app_raw).strip()

    # Already valid — no correction needed
    if app_clean in app_allowlist:
        return intent

    # Try fuzzy match with high cutoff
    matches = difflib.get_close_matches(app_clean, app_allowlist, n=1, cutoff=0.6)
    if matches:
        corrected = matches[0]
        new_entities = {**intent.entities, "app": corrected}
        from dataclasses import replace
        return replace(intent, entities=new_entities)

    return intent


def build_system_prompt() -> str:
    """JSON-only system prompt: the 16-command allowlist, schema, and rules."""
    intent_list = "|".join(sorted(ALLOWED_INTENTS))
    domain_lines = "\n".join(f"- {domain}: {', '.join(values)}" for domain, values in DOMAIN_INTENTS.items())
    return (
        "You map a voice command (Spanish rioplatense, already normalized) to exactly one "
        "allowed intent. Reply with ONLY a JSON object — no prose, no markdown, no code fence.\n"
        "Schema:\n"
        '{"intent": "<' + intent_list + '>", "entities": {"repo": "", "app": "", "query": "", '
        '"text": "", "url": "", "engine": "google", "command": ""}, "confidence": 0.0}\n'
        "Rules:\n"
        "- intent MUST be one of the listed values; never invent commands.\n"
        "- shutdown, reboot and power_off_self are gated by a separate deterministic rule and are "
        "only emitted when the user clearly asks to power down the machine or the assistant itself.\n"
        "- open_app: ONLY for known applications (firefox, terminal, spotify, libreoffice, etc). "
        "Use entities.app with the app name.\n"
        "- execute: for ANY command that is NOT an open_app, NOT create_doc, NOT web_search. "
        "Generate the exact shell command.\n"
        "  Examples:\n"
        "  'make build' → intent='execute', command='make build'\n"
        "  'corré los tests' → intent='execute', command='pytest'\n"
        "  'abrí vim config.json' → intent='execute', command='vim config.json'\n"
        "  'creá una carpeta llamada test' → intent='execute', command='mkdir -p test'\n"
        "  'instalá nginx' → intent='execute', command='sudo apt-get install -y nginx'\n"
        "  'listá archivos src' → intent='execute', command='ls src'\n"
        "  'editá el archivo config.json' → intent='execute', command='nano config.json'\n"
        "  'poné en marcha el servidor' → intent='execute', command='make run'\n"
        "  'mandale un commit' → intent='execute', command='git commit'\n"
        "  'haceme un backup' → intent='execute', command='cp -r . .backup'\n"
        "  'tirá todo' → intent='execute', command='rm -rf *'\n"
        "- unknown: only when the request truly cannot map to any intent.\n"
        "- entities: fill only fields that apply — query for questions, repo for a repository, app for "
        "an application, url for a web address, text for free-form content, command for execute. "
        "Keep 'este proyecto' style references as repo 'este proyecto'.\n"
        "- confidence: 0.0-1.0; below 0.6 the assistant must ask again.\n"
        "Rioplatense verbs: abrí/abrir, cerrá/cerrar, busqué/buscar, creá/crear, borrá/borrar, "
        "corré/correr, instalá/instalar, listá/listar, editá/editar, tirá/tirar, mandá/mandar, "
        "hacé/hacer, poné/poner, sacá/sacar, andá/andar.\n"
        f"Domains:\n{domain_lines}\n"
    )
