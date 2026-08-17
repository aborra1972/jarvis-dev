"""Interpreter orchestration (PR2, task 2.5): normalize → golden → LLM fallback.

Composes the pure stages into the final Interpretation. Destructive intents
only ever come from the golden hard gate: if the LLM suggests one without a
golden match it is rejected (spec: golden rejection wins over LLM suggestion).
The execute intent is a special case: it generates shell commands via Ollama
and runs with confirmation (Option A) or auto (Option B).
"""

from __future__ import annotations

import collections
import difflib
import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass, replace

from jarvis import config as _config
from jarvis.interpreter import golden, llm, schema
from jarvis.interpreter.focus import is_code_editor_focused
from jarvis.interpreter.normalize import normalize

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


@dataclass
class Interpretation:
    """Final interpreter result; at most one of intent/reask signals applies."""

    intent: schema.Intent | None = None
    needs_reask: bool = False
    rejected_destructive: bool = False
    unsupported: bool = False
    reason: str = ""


def resolve_intent(
    text: str,
    provider: llm.IntentProvider | None = None,
    app_allowlist: set[str] | None = None,
    threshold: float = schema.CONFIDENCE_THRESHOLD,
    use_cache: bool = True,
) -> Interpretation:
    """Resolve a raw transcript to an Interpretation (never emits unvalidated intents)."""
    allowlist = _config.ALLOWED_APPS if app_allowlist is None else app_allowlist

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
    if use_cache and provider is not None:
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
        hit = _resolve_active_project(hit)
        # Fuzzy-correct app names before validation
        hit = schema.fuzzy_correct_entities(hit, allowlist)
        invalid = schema.validate_entities(hit, allowlist)
        if invalid:
            return Interpretation(needs_reask=True, reason=f"invalid_entity:{','.join(invalid)}")
        return Interpretation(intent=hit)

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
        intent = llm.resolve(surface, schema.build_system_prompt(), provider)
    except schema.SchemaError as exc:
        if exc.code == "unknown_intent":
            return Interpretation(unsupported=True, reason="unknown_intent")
        return Interpretation(needs_reask=True, reason=exc.code)
    except Exception:
        return Interpretation(needs_reask=True, reason="llm_failure")

    intent = replace(intent, source="llm")

    # 3. Hard gate over LLM output: destructive intents without a golden match
    #    are REJECTED (spec: golden rejection wins over LLM suggestion).
    if intent.intent in schema.DESTRUCTIVE_INTENTS:
        return Interpretation(
            needs_reask=True, rejected_destructive=True, reason="golden_rejected_destructive"
        )
    if intent.intent == "unknown":
        return Interpretation(needs_reask=True, reason="unknown")

    # 3b. Fix LLM routing: if create_artifact includes a command field, reroute to execute
    if intent.intent == "create_artifact" and intent.entities.get("command"):
        intent = replace(intent, intent="execute")

    # 3c. Route general_qa: if code editor is focused, reroute to ask (OpenCode)
    #     Otherwise keep as general_qa for direct LLM response
    if intent.intent == "general_qa":
        if is_code_editor_focused():
            logger.info("code editor focused — routing general_qa to ask (OpenCode)")
            intent = replace(intent, intent="ask")

    # 4. Execute intent: set confirm_required based on AUTO_EXECUTE config.
    #    Option A (AUTO_EXECUTE=False): confirm_required=True → orchestrator asks
    #    Option B (AUTO_EXECUTE=True): confirm_required=False → direct execution
    if intent.intent == "execute":
        if not _config.AUTO_EXECUTE:
            intent = replace(intent, confirm_required=True)

    intent = _resolve_active_project(intent)

    # 5. Cache successful resolution for repeat commands
    if use_cache and intent.confidence >= threshold:
        _intent_cache.put(surface, intent)

    return _validate_and_wrap(intent, allowlist, threshold)


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


def _resolve_active_project(intent: schema.Intent) -> schema.Intent:
    """Delegation: pointer repo references → active project (orchestrator PR3)."""
    if intent.intent == "open_repo" and intent.entities.get("repo", "").strip().lower() in ACTIVE_PROJECT_ALIASES:
        return replace(
            intent, entities={**intent.entities, "repo": ""}, use_active_project=True
        )
    return intent
