"""Name gate for bare-name wake activation (engine "name").

The user activates the assistant by speaking its name at the START of the
utterance ("friday, abri firefox"). After STT, strip_agent_prefix() verifies
the first word against the active agent's name and returns the command
without it; None means the utterance does not start with the name and must
be discarded silently (it was ambient speech, not an activation).
"""

from __future__ import annotations

_WORD_PUNCTUATION = " \t,.;:!?¡¿"


def strip_agent_prefix(transcript: str, name: str) -> str | None:
    """Return the command after the agent name, or None when it does not start
    with the name.

    The first word is compared case-insensitively and tolerance to trailing
    punctuation ("friday," == "Friday"). A bare name with no command
    ("friday") also returns None: there is no request to act on.
    """
    text = transcript.strip() if transcript else ""
    if not text:
        return None
    first, _, rest = text.partition(" ")
    if first.strip(_WORD_PUNCTUATION).lower() != name.lower():
        return None
    remainder = rest.strip(_WORD_PUNCTUATION)
    return remainder or None