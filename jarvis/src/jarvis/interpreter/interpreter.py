"""Interpreter orchestration (PR2, task 2.5): normalize → golden → LLM fallback.

Composes the pure stages into the final Interpretation. Destructive intents
only ever come from the golden hard gate: if the LLM suggests one without a
golden match it is rejected (spec: golden rejection wins over LLM suggestion).
The execute intent is a special case: it generates shell commands via Ollama
and runs with confirmation (Option A) or auto (Option B).
"""

from __future__ import annotations

import collections
from datetime import datetime
import hashlib
import logging
import re
import threading
import time
from typing import Callable
from dataclasses import dataclass, replace

from jarvis import config as _config
from jarvis.interpreter import golden, llm, nlu, schema
from jarvis.interpreter.focus import is_code_editor_focused
from jarvis.interpreter.normalize import normalize, normalize_boundary

GOODBYE_PHRASES: frozenset[str] = frozenset({"terminamos", "hasta luego"})
_TERMINAL_STT_PUNCTUATION = ".!?¡¿"


def _goodbye_boundary_surface(text: str) -> str:
    """Normalize only outer space/case plus terminal STT punctuation."""
    return normalize_boundary(text).rstrip(_TERMINAL_STT_PUNCTUATION).strip()


def is_goodbye(text: str) -> bool:
    """Return true only for an exact, standalone goodbye transcript."""
    return _goodbye_boundary_surface(text) in GOODBYE_PHRASES

logger = logging.getLogger("jarvis.interpreter")

# Empty/pointer repo references → delegate the active project to the
# orchestrator (PR3 session state); the interpreter never guesses a path.
ACTIVE_PROJECT_ALIASES: frozenset[str] = frozenset({
    "", "este", "este proyecto", "este repo", "este repositorio",
    "el proyecto", "el repo", "el repositorio", "el proyecto actual",
    "actual", "aca", "aqui", "acá", "aquí",
})


class _IntentCache:
    """Thread-safe LRU-ish cache for LLM intent resolutions.

    Maps normalized text → cached Intent for a configurable TTL.
    Prevents redundant LLM calls for repeat commands (e.g. "abrí la
    terminal" said multiple times). Max 256 entries to bound memory.
    """

    def __init__(self, ttl_s: float = 300.0, max_size: int = 256) -> None:
        self._ttl = ttl_s
        self._max_size = max_size
        self._lock = threading.Lock()
        # {key: (timestamp, Intent)}
        self._cache: dict[str, tuple[float, schema.Intent]] = {}

    def _key(self, text: str) -> str:
        # Fast hash for cache key — normalize case + whitespace
        normalized = " ".join(text.lower().split())
        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def get(self, text: str) -> schema.Intent | None:
        """Return cached intent if fresh, else None."""
        key = self._key(text)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, intent = entry
            if time.monotonic() - ts > self._ttl:
                del self._cache[key]
                return None
            return intent

    def put(self, text: str, intent: schema.Intent) -> None:
        """Cache an intent. Evicts oldest if over max_size."""
        key = self._key(text)
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest entry
                oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
                del self._cache[oldest_key]
            self._cache[key] = (time.monotonic(), intent)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()


# Global cache instance — 5 min TTL, max 256 entries
_intent_cache = _IntentCache()


class _GeneralQaCache:
    """Thread-safe bounded cache for validated, static Codex answers only."""

    def __init__(self, ttl_s: float = 300.0, max_size: int = 128) -> None:
        self._ttl = ttl_s
        self._max_size = max_size
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, schema.Intent, str]] = {}

    def get(self, key: str) -> tuple[schema.Intent, str] | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            timestamp, intent, answer = entry
            if time.monotonic() - timestamp > self._ttl:
                del self._cache[key]
                return None
            return intent, answer

    def put(self, key: str, intent: schema.Intent, answer: str) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                oldest = min(self._cache, key=lambda item: self._cache[item][0])
                del self._cache[oldest]
            self._cache[key] = (time.monotonic(), intent, answer)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_general_qa_cache = _GeneralQaCache()

_GENERAL_QA_PREFIXES = ("que es ", "que significa ", "definime ")
_GENERAL_QA_EXCLUSIONS = frozenset({
    "hora", "fecha", "dia", "clima", "temperatura", "pronostico", "hoy",
    "ayer", "manana", "ahora", "actual", "noticia", "buscar", "busca",
    "internet", "web", "abrir", "abre", "cerrar", "cierra", "apagar", "apaga",
    "reiniciar", "reinicia", "borrar", "borra", "eliminar", "elimina",
    "ejecutar", "ejecuta", "comando", "terminal", "por", "favor",
})


def _static_general_qa_key(surface: str) -> str | None:
    """Return an exact key only for explicitly stable, safe question forms."""
    if not any(surface.startswith(prefix) for prefix in _GENERAL_QA_PREFIXES):
        return None
    words = surface.split()
    if len(words) < 3 or any(word in _GENERAL_QA_EXCLUSIONS for word in words):
        return None
    # The normalized surface itself is the key: no fuzzy or prefix matching.
    return surface


class _RecentContext:
    """Thread-safe deque of recent intents for pronoun resolution.

    Stores the last N intents so that pronouns like "lo", "la", "el", "ella"
    can be resolved to the most recent entity. For example:
    - User: "abrí firefox" → intent=open_app, app=firefox
    - User: "cerralo" → resolve "lo" → firefox → intent=execute, command="pkill firefox"
    """

    def __init__(self, max_size: int = 5) -> None:
        self._lock = threading.Lock()
        self._history: collections.deque[schema.Intent] = collections.deque(maxlen=max_size)

    def push(self, intent: schema.Intent) -> None:
        """Store a successful intent in the history."""
        with self._lock:
            self._history.append(intent)

    def resolve_pronoun(self, text: str) -> str | None:
        """If text contains a pronoun, try to resolve it to the last entity.

        Returns the resolved text or None if no resolution is possible.
        """
        with self._lock:
            if not self._history:
                return None
            last = self._history[-1]

        # Detect pronouns in the text
        pronouns = re.compile(
            r'\b(lo|la|los|las|el|ella|esto|eso)\b',
            re.IGNORECASE,
        )
        if not pronouns.search(text):
            return None

        # Try to resolve based on the last intent type
        if last.intent == "open_app" and "app" in last.entities:
            app = last.entities["app"]
            # "cerralo" → "cerrar <app>"
            text = re.sub(
                r'\b(cerr(?:ar|á|ame|alo))\s+(?:lo|la|el|ella|esto|eso)\b',
                f'cerrar {app}',
                text,
                flags=re.IGNORECASE,
            )
            # "abrirlo" → "abrir <app>"
            text = re.sub(
                r'\b(abrir(?:lo|me)?)\s+(?:lo|la|el|ella|esto|eso)\b',
                f'abrir {app}',
                text,
                flags=re.IGNORECASE,
            )
            return text

        if last.intent == "open_repo" and "repo" in last.entities:
            repo = last.entities["repo"]
            if repo:
                text = re.sub(
                    r'\b(abrir(?:lo|me)?)\s+(?:lo|la|el|ella|esto|eso)\b',
                    f'abrir el proyecto {repo}',
                    text,
                    flags=re.IGNORECASE,
                )
                return text

        return None


# Global recent context — last 5 intents
_recent_context = _RecentContext()


def _guess(surface: str) -> str | None:
    """Best-effort spoken hint from interpreter.nlu, or None.

    Called only after BOTH the golden gate and the LLM have already failed
    to resolve `surface` — this never runs on the happy path, so its cost
    (a small TF-IDF+LogReg inference) is paid only when Jarvis was already
    about to say "no entiendo". Must never raise: nlu.classify() is
    documented best-effort and returns None on any internal failure.
    """
    suggestion = nlu.classify(surface)
    return suggestion.spoken if suggestion else None


@dataclass
class Interpretation:
    """Final interpreter result; at most one of intent/reask signals applies."""

    intent: schema.Intent | None = None
    needs_reask: bool = False
    unsupported: bool = False
    reason: str = ""
    rejected_destructive: bool = False
    # Non-executable hint from interpreter.nlu (roadmap: NLU classifier).
    # Only ever set alongside needs_reask/unsupported — the orchestrator may
    # SPEAK this, never execute it. See interpreter/nlu.py's module docstring.
    suggestion: str | None = None
    answer: str | None = None
    control: str | None = None


def resolve_intent(
    text: str,
    provider: llm.IntentProvider | None = None,
    app_allowlist: set[str] | None = None,
    threshold: float = schema.CONFIDENCE_THRESHOLD,
    use_cache: bool = True,
    now: Callable[[], datetime] | None = None,
) -> Interpretation:
    """Resolve a raw transcript to an Interpretation (never emits unvalidated intents)."""
    allowlist = _config.ALLOWED_APPS if app_allowlist is None else app_allowlist

    # Lifecycle controls are deterministic and must precede every ordinary route.
    if is_goodbye(text):
        logger.info("goodbye.accepted(source=voice)")
        return Interpretation(control="goodbye")
    boundary_surface = normalize_boundary(text)
    if any(phrase in boundary_surface for phrase in GOODBYE_PHRASES):
        logger.info("goodbye.rejected(reason=nonstandalone)")

    # Natural surface (no verb canonicalization): golden patterns now accept
    # rioplatense variants via _verb_alt, so free-text entities (ask/web_search
    # queries) keep the user's original wording instead of corrupted verb forms.
    surface = normalize(text, canonicalize=False)
    if not surface:
        return Interpretation(needs_reask=True, reason="empty")

    # 0b. Recent context: try to resolve pronouns (e.g. "cerralo" → "cerrar firefox")
    resolved = _recent_context.resolve_pronoun(surface)
    if resolved is not None:
        surface = resolved
        logger.debug("pronoun resolved to: %r", surface)

    # 0. Intent cache: skip LLM for repeat commands (5 min TTL)
    if use_cache and provider is not None and not _is_codex_provider(provider):
        cached = _intent_cache.get(surface)
        if cached is not None:
            logger.debug("cache hit for %r", surface)
            # Apply fuzzy correction (cache may have been stored before correction)
            corrected = schema.fuzzy_correct_entities(cached, allowlist)
            if corrected is not cached:
                corrected = replace(corrected, source="cache+fuzzy")
            else:
                corrected = replace(corrected, source="cache")
            return _validate_and_wrap(corrected, allowlist, threshold)

    # 1. Golden gate FIRST — authoritative for destructive intents (ADR-2).
    hit = golden.gate(surface)
    if hit is not None:
        if hit.confirm_required:
            return Interpretation(intent=hit)  # destructive: LLM never consulted
        local_kind = hit.entities.get("local_answer")
        if hit.intent == "general_qa" and local_kind:
            answer = _local_datetime_answer(local_kind, now=now)
            return Interpretation(intent=hit, answer=answer)
        hit = _resolve_active_project(hit)
        # Fuzzy-correct app names before validation
        hit = schema.fuzzy_correct_entities(hit, allowlist)
        invalid = schema.validate_entities(hit, allowlist)
        if invalid:
            return Interpretation(needs_reask=True, reason=f"invalid_entity:{','.join(invalid)}")
        return Interpretation(intent=hit)

    # Exact static-QA cache is deliberately after the golden gate so local
    # fast paths and all command/safety routes remain authoritative.
    static_qa_key = _static_general_qa_key(surface) if use_cache and _is_codex_provider(provider) else None
    if static_qa_key is not None:
        cached_qa = _general_qa_cache.get(static_qa_key)
        if cached_qa is not None:
            cached_intent, cached_answer = cached_qa
            cached_intent = replace(cached_intent, source="cache")
            result = _validate_and_wrap(cached_intent, allowlist, threshold)
            if result.intent is not None:
                result.answer = cached_answer
            return result

    # 2. LLM fallback for everything else (non-destructive).
    if provider is None:
        return Interpretation(needs_reask=True, reason="no_provider")

    # Truncate long transcripts to avoid feeding noise/radio to the LLM.
    # 200 chars is enough for any real voice command; anything longer is
    # likely background noise that Whisper captured by mistake.
    MAX_TRANSCRIPT_CHARS = 200
    if len(surface) > MAX_TRANSCRIPT_CHARS:
        surface = surface[:MAX_TRANSCRIPT_CHARS]

    try:
        combined_qa = _is_codex_provider(provider)
        system_prompt = (
            schema.build_codex_system_prompt()
            if combined_qa
            else schema.build_system_prompt(include_general_qa_answer=False)
        )
        payload = llm.resolve_payload(surface, system_prompt, provider)
        intent = schema.validate(payload)
        answer = _qa_answer(payload) if intent.intent == "general_qa" else None
    except schema.SchemaError as exc:
        if exc.code == "unknown_intent":
            return Interpretation(
                unsupported=True, reason="unknown_intent", suggestion=_guess(surface)
            )
        return Interpretation(needs_reask=True, reason=exc.code)
    except Exception:
        return Interpretation(needs_reask=True, reason="llm_failure")

    intent = replace(intent, source="llm")

    # 3. Hard gate over LLM output: destructive intents without a golden match
    #    are REJECTED (spec: golden rejection wins over LLM suggestion).
    if schema.is_destructive_intent(intent.intent):
        return Interpretation(
            needs_reask=True, rejected_destructive=True, reason="golden_rejected_destructive"
        )
    if intent.intent == "unknown":
        return Interpretation(needs_reask=True, reason="unknown", suggestion=_guess(surface))

    # 3b. Fix LLM routing: if create_artifact includes a command field, reroute to execute
    if intent.intent == "create_artifact" and intent.entities.get("command"):
        intent = replace(intent, intent="execute")

    # 3c. Route general_qa: if code editor is focused, reroute to ask (OpenCode)
    #     Otherwise keep as general_qa for direct LLM response
    if intent.intent == "general_qa":
        if is_code_editor_focused():
            logger.info("code editor focused — routing general_qa to ask (OpenCode)")
            intent = replace(intent, intent="ask")
            answer = None

    # 4. Execute intent: confirmation policy driven by SAFETY_GATE (T-SAFE-02).
    #    - "strict" (default) → always confirm every execute command.
    #    - "auto" → follow AUTO_EXECUTE; dangerous-pattern commands always
    #      confirm even in auto mode (AUTO_EXECUTE is meant to skip the prompt
    #      for routine commands (ls, git status, ...), not to silently
    #      green-light `find . -exec rm -rf {} +` or `chmod -R 777 /`).
    #    - "yolo" → never confirm routine commands; dangerous commands keep
    #      confirming. Destructive golden-gate intents are NOT affected: they
    #      already carry confirm_required=True at the gate and never reach
    #      this LLM-only step ("yolo acelera lo rutinario, no desbloquea lo
    #      destructivo").
    if intent.intent == "execute":
        command_str = intent.entities.get("command", "")
        if _config.SAFETY_GATE == "yolo":
            if schema.is_dangerous_command(command_str):
                intent = replace(intent, confirm_required=True)
        elif _config.SAFETY_GATE == "auto":
            if not _config.AUTO_EXECUTE or schema.is_dangerous_command(command_str):
                intent = replace(intent, confirm_required=True)
        else:  # "strict" (default): always confirm execute.
            intent = replace(intent, confirm_required=True)

    intent = _resolve_active_project(intent)

    result = _validate_and_wrap(intent, allowlist, threshold)
    if result.intent is not None and intent.intent == "general_qa":
        result.answer = answer
        # Cache only after all schema/entity/confidence validation succeeds.
        if static_qa_key is not None and answer is not None and len(answer) <= 2000:
            _general_qa_cache.put(static_qa_key, intent, answer)
    elif use_cache and intent.confidence >= threshold:
        _intent_cache.put(surface, intent)
    return result


def _validate_and_wrap(
    intent: schema.Intent,
    allowlist: set[str],
    threshold: float,
) -> Interpretation:
    """Validate entities and wrap into Interpretation. Shared by cache + LLM paths."""
    if intent.confidence < threshold:
        return Interpretation(needs_reask=True, reason="low_confidence")
    invalid = schema.validate_entities(intent, allowlist)
    if invalid:
        return Interpretation(needs_reask=True, reason=f"invalid_entity:{','.join(invalid)}")
    # Push successful intent to recent context for pronoun resolution
    _recent_context.push(intent)
    return Interpretation(intent=intent)


def _is_codex_provider(provider: object) -> bool:
    return isinstance(provider, llm.CodexProvider)


def _local_datetime_answer(kind: str, *, now: Callable[[], datetime] | None = None) -> str:
    """Format the host-local date/time for exact golden local-QA forms."""
    current = (now or (lambda: datetime.now().astimezone()))()
    weekdays = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    months = (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    )
    if kind == "time":
        return f"Son las {current.hour:02d}:{current.minute:02d}."
    if kind == "weekday":
        return f"Hoy es {weekdays[current.weekday()]}."
    return f"Hoy es {current.day} de {months[current.month - 1]} de {current.year}."


def _qa_answer(payload: dict) -> str | None:
    answer = payload.get("answer")
    if not isinstance(answer, str):
        return None
    answer = answer.strip()
    return answer if answer and len(answer) <= 2000 else None


def _resolve_active_project(intent: schema.Intent) -> schema.Intent:
    """Delegation: pointer repo references → active project (orchestrator PR3)."""
    if intent.intent == "open_repo" and intent.entities.get("repo", "").strip().lower() in ACTIVE_PROJECT_ALIASES:
        return replace(
            intent, entities={**intent.entities, "repo": ""}, use_active_project=True
        )
    return intent
