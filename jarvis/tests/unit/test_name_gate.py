"""Name gate tests (feature "wake por nombre", engine "name").

The name and the command are ONE utterance ("friday, abrí firefox"), so after
STT the loop must verify the transcript starts with the active agent's name and
strip it before interpretation. strip_agent_prefix() is the pure core of that
gate: None means the utterance didn't start with the name and must be discarded
silently (it was ambient speech, not an activation).
"""

from __future__ import annotations

from jarvis.orchestrator.name_gate import strip_agent_prefix


def test_strips_name_with_comma() -> None:
    assert strip_agent_prefix("friday, abrí firefox", "Friday") == "abrí firefox"


def test_strips_name_case_insensitive() -> None:
    assert strip_agent_prefix("FRIDAY abrí firefox", "friday") == "abrí firefox"


def test_strips_name_without_comma() -> None:
    assert strip_agent_prefix("friday abre firefox", "Friday") == "abre firefox"


def test_accepts_explicit_jarvis_whisper_aliases() -> None:
    assert strip_agent_prefix("Yarvis, abrí firefox", "Jarvis") == "abrí firefox"
    assert strip_agent_prefix("Charvis, abrí firefox", "Jarvis") == "abrí firefox"
    assert strip_agent_prefix("Jaarvis, abrí firefox", "Jarvis") == "abrí firefox"


def test_name_not_at_start_is_none() -> None:
    assert strip_agent_prefix("cómo estás friday", "friday") is None


def test_hey_prefix_not_accepted() -> None:
    """Bare-name mode does not accept "hey" — only the bare agent name fires."""
    assert strip_agent_prefix("hey friday, hacé algo", "friday") is None


def test_bare_name_without_command_is_none() -> None:
    assert strip_agent_prefix("jarvis", "Jarvis") is None


def test_bare_name_with_punctuation_is_none() -> None:
    assert strip_agent_prefix("friday!", "friday") is None


def test_empty_or_none_transcript_is_none() -> None:
    assert strip_agent_prefix("", "friday") is None
    assert strip_agent_prefix(None, "friday") is None