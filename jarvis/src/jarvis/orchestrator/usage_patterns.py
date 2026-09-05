"""Usage-pattern memory ("memoria de patrones de uso").

Boot-time module: reads the transcripts journal, looks for intents the user
repeats across sessions, and suggests the most frequent one back with a
friendly Spanish note — so Jarvis can offer to turn a habit into a shortcut.

State: the suggestion state file (``usage_suggestions.json``) remembers the
count at which each pattern was last suggested, so boot never nags with the
identical note until the pattern actually grows again (see
``pick_new_suggestion``'s ``re_suggest_delta``).

Everything here is best-effort: a missing/corrupt journal or state file must
never crash the boot sequence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Intents that are deliberately never tracked. general_qa is at the top of
# the list: free-text queries rarely repeat identically, and grouping them
# would lump unrelated questions together.
EXCLUDED_INTENTS = {"general_qa", "off", "switch_on", "switch_off", "confirm"}

DEFAULT_MIN_COUNT = 5
DEFAULT_RE_SUGGEST_DELTA = 3
DEFAULT_LIMIT = 3


def _pattern_key(intent: str, entities: dict[str, Any]) -> str:
    """Deterministic key for one (intent, entities) pattern."""

    return json.dumps({"intent": intent, "entities": entities}, sort_keys=True)


def top_patterns(
    journal: Path | str,
    min_count: int = DEFAULT_MIN_COUNT,
    limit: int = DEFAULT_LIMIT,
) -> list[tuple[str, dict[str, Any], int]]:
    """Return ``(intent, entities, count)`` for the most repeated patterns.

    - ``general_qa`` (and other excluded intents) are never counted.
    - Lines without an ``entities`` key default to ``{}`` (pre-feature
      journal format) — they collapse into one degenerate pattern but never
      raise.
    - Corrupt JSON lines, blank lines and a missing journal are skipped.
    - Results are ordered by frequency (descending), then journal order.

    ``min_count`` is a hard floor: anything below it is not a "pattern".
    """

    counts: dict[str, list[Any]] = {}
    try:
        text = Path(journal).read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        intent = entry.get("intent")
        if not intent or intent in EXCLUDED_INTENTS:
            continue
        entities = entry.get("entities")
        if not isinstance(entities, dict):
            entities = {}
        key = _pattern_key(intent, entities)
        if key not in counts:
            counts[key] = [intent, entities, 0]
        counts[key][2] += 1

    ranked = sorted(counts.values(), key=lambda c: c[2], reverse=True)
    return [
        (intent, entities, n)
        for intent, entities, n in ranked
        if n >= min_count
    ][:limit]


def describe_pattern(intent: str, entities: dict[str, Any], count: int) -> str:
    """One friendly Spanish sentence describing a repeated pattern."""

    if intent == "open_app":
        return f"noté que abriste {entities.get('app', 'una app')} {count} veces"
    if intent == "execute":
        return f'noté que corriste "{entities.get("command", "")}" {count} veces'
    if intent == "web_search":
        return f'buscaste "{entities.get("query", "")}" {count} veces'
    if intent == "open_repo":
        return f"abriste {entities.get('repo', 'un repo')} {count} veces"
    return f"repetiste ese comando {count} veces"


def _load_suggested_state(state_path: Path) -> dict[str, int]:
    """Read the previous suggestion state; corrupt or missing → empty."""

    try:
        data = json.loads(Path(state_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, (int, float))}
    except (OSError, ValueError):
        pass
    return {}


def _save_suggested_state(state_path: Path, state: dict[str, int]) -> None:
    """Best-effort persist; a failed save must never crash boot."""

    try:
        state_path = Path(state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
    except OSError:
        pass


def pick_new_suggestion(
    journal: Path | str,
    state: Path | str,
    min_count: int = DEFAULT_MIN_COUNT,
    re_suggest_delta: int = DEFAULT_RE_SUGGEST_DELTA,
) -> str | None:
    """Return a suggestion note for the top pattern, or None when quiet.

    A pattern is suggested only when:
    - it hits ``min_count`` uses, AND
    - it was never suggested before, or its count grew by at least
      ``re_suggest_delta`` since the last time it was suggested.

    When a note IS returned, the new count is persisted to ``state`` so a
    restart doesn't repeat the identical note on every boot.
    """

    journal_path = Path(journal)
    try:
        if not journal_path.is_file():
            return None
    except OSError:
        return None

    patterns = top_patterns(journal_path, min_count=min_count, limit=1)
    if not patterns:
        return None
    intent, entities, count = patterns[0]

    suggested = _load_suggested_state(Path(state))
    key = _pattern_key(intent, entities)
    last = suggested.get(key)
    if last is not None and count < last + re_suggest_delta:
        return None

    suggested[key] = count
    _save_suggested_state(Path(state), suggested)
    return describe_pattern(intent, entities, count)