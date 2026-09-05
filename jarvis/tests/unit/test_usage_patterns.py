"""Tests for orchestrator.usage_patterns ("memoria de patrones de uso").

This module had zero test coverage before — it's fully implemented and
wired into loop.py's boot sequence (pick_new_suggestion is called right
after the ANNOUNCEMENT), but nothing verified it actually behaves as the
docstrings claim. These tests lock in that behavior.
"""

from __future__ import annotations

import json
from pathlib import Path

from jarvis.orchestrator import usage_patterns as up


def _write_journal(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


# --- top_patterns --------------------------------------------------------


def test_top_patterns_counts_repeated_entities(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(
        journal,
        [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6
        + [{"intent": "open_app", "entities": {"app": "spotify"}}] * 2,
    )

    results = up.top_patterns(journal, min_count=5)

    assert results == [("open_app", {"app": "firefox"}, 6)]


def test_top_patterns_ignores_untracked_intents(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    # general_qa is deliberately excluded (free-text query rarely repeats
    # identically, and grouping it would lump unrelated questions together)
    _write_journal(
        journal, [{"intent": "general_qa", "entities": {"query": "que hora es"}}] * 10
    )

    assert up.top_patterns(journal, min_count=5) == []


def test_top_patterns_distinguishes_different_entities_same_intent(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(
        journal,
        [{"intent": "open_app", "entities": {"app": "firefox"}}] * 5
        + [{"intent": "open_app", "entities": {"app": "code"}}] * 5,
    )

    results = up.top_patterns(journal, min_count=5, limit=5)

    assert len(results) == 2
    apps = {entities["app"] for _, entities, _ in results}
    assert apps == {"firefox", "code"}


def test_top_patterns_respects_limit_and_orders_by_frequency(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(
        journal,
        [{"intent": "open_app", "entities": {"app": "a"}}] * 9
        + [{"intent": "open_app", "entities": {"app": "b"}}] * 7
        + [{"intent": "open_app", "entities": {"app": "c"}}] * 5,
    )

    results = up.top_patterns(journal, min_count=5, limit=2)

    assert [entities["app"] for _, entities, _ in results] == ["a", "b"]


def test_top_patterns_below_min_count_excluded(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 4)

    assert up.top_patterns(journal, min_count=5) == []


def test_top_patterns_missing_file_returns_empty(tmp_path: Path) -> None:
    assert up.top_patterns(tmp_path / "does-not-exist.jsonl") == []


def test_top_patterns_skips_corrupt_lines(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    journal.write_text(
        "not valid json\n"
        + "\n".join(
            json.dumps({"intent": "open_app", "entities": {"app": "firefox"}})
            for _ in range(5)
        )
        + "\n"
    )

    assert up.top_patterns(journal, min_count=5) == [
        ("open_app", {"app": "firefox"}, 5)
    ]


def test_top_patterns_skips_entries_without_entities_key(tmp_path: Path) -> None:
    """Journal lines from before this feature existed have no 'entities' key."""
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(journal, [{"intent": "open_app"}] * 5)

    # Missing entities defaults to {} — these all collapse into one pattern
    # with empty entities, which is degenerate but must not raise.
    results = up.top_patterns(journal, min_count=5)
    assert results == [("open_app", {}, 5)]


# --- describe_pattern ------------------------------------------------------


def test_describe_pattern_open_app() -> None:
    assert up.describe_pattern("open_app", {"app": "firefox"}, 6) == (
        "noté que abriste firefox 6 veces"
    )


def test_describe_pattern_execute() -> None:
    result = up.describe_pattern("execute", {"command": "git status"}, 5)
    assert result == 'noté que corriste "git status" 5 veces'


def test_describe_pattern_web_search() -> None:
    result = up.describe_pattern("web_search", {"query": "clima"}, 5)
    assert result == 'buscaste "clima" 5 veces'


def test_describe_pattern_open_repo() -> None:
    result = up.describe_pattern("open_repo", {"repo": "jarvis-dev"}, 5)
    assert result == "abriste jarvis-dev 5 veces"


def test_describe_pattern_unknown_intent_has_generic_fallback() -> None:
    result = up.describe_pattern("mystery_intent", {}, 5)
    assert result == "repetiste ese comando 5 veces"


# --- pick_new_suggestion ---------------------------------------------------


def test_pick_new_suggestion_returns_none_below_threshold(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 3)

    assert up.pick_new_suggestion(journal, state, min_count=5) is None


def test_pick_new_suggestion_first_time_returns_note(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)

    note = up.pick_new_suggestion(journal, state, min_count=5)

    assert note == "noté que abriste firefox 6 veces"


def test_pick_new_suggestion_does_not_repeat_same_count(tmp_path: Path) -> None:
    """Jarvis must not nag with the identical suggestion every single boot."""
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)

    first = up.pick_new_suggestion(journal, state, min_count=5)
    second = up.pick_new_suggestion(journal, state, min_count=5)

    assert first is not None
    assert second is None


def test_pick_new_suggestion_re_suggests_after_delta_growth(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)
    up.pick_new_suggestion(journal, state, min_count=5, re_suggest_delta=3)

    # Only +2 more uses — below the re_suggest_delta of 3, should stay quiet
    with journal.open("a", encoding="utf-8") as handle:
        for _ in range(2):
            handle.write(
                json.dumps({"intent": "open_app", "entities": {"app": "firefox"}}) + "\n"
            )
    quiet = up.pick_new_suggestion(journal, state, min_count=5, re_suggest_delta=3)
    assert quiet is None

    # One more use tips it over the +3 delta (8 total, was last suggested at 6)
    with journal.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"intent": "open_app", "entities": {"app": "firefox"}}) + "\n")
    note = up.pick_new_suggestion(journal, state, min_count=5, re_suggest_delta=3)
    assert note == "noté que abriste firefox 9 veces"


def test_pick_new_suggestion_persists_state_across_calls(tmp_path: Path) -> None:
    """A fresh process (new pick_new_suggestion call) must still remember
    what was already suggested, since the state is read from disk each time
    — this is what makes the "don't nag every boot" behavior actually work
    across `jarvis start` restarts, not just within one Python process."""
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)

    up.pick_new_suggestion(journal, state, min_count=5)
    assert state.is_file()
    saved = json.loads(state.read_text())
    assert saved == {up._pattern_key("open_app", {"app": "firefox"}): 6}


def test_pick_new_suggestion_missing_journal_returns_none(tmp_path: Path) -> None:
    assert up.pick_new_suggestion(
        tmp_path / "no-journal.jsonl", tmp_path / "state.json"
    ) is None


def test_pick_new_suggestion_corrupt_state_file_does_not_raise(tmp_path: Path) -> None:
    journal = tmp_path / "transcripts.jsonl"
    state = tmp_path / "usage_suggestions.json"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)
    state.write_text("{ not valid json")

    # Corrupt state is treated as empty — still returns a suggestion instead
    # of raising, matching _load_suggested_state's documented fallback.
    note = up.pick_new_suggestion(journal, state, min_count=5)
    assert note == "noté que abriste firefox 6 veces"


def test_pick_new_suggestion_unwritable_state_dir_does_not_raise(tmp_path: Path) -> None:
    """_save_suggested_state is documented best-effort: a failed save must
    not crash boot, it just means the suggestion might repeat next time."""
    journal = tmp_path / "transcripts.jsonl"
    _write_journal(journal, [{"intent": "open_app", "entities": {"app": "firefox"}}] * 6)
    # A path where the parent can never be created (file exists in its place)
    blocked_parent = tmp_path / "not_a_dir"
    blocked_parent.write_text("i'm a file, not a directory")
    state = blocked_parent / "usage_suggestions.json"

    note = up.pick_new_suggestion(journal, state, min_count=5)
    assert note == "noté que abriste firefox 6 veces"
