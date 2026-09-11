"""Local deletable logs (RNF-3 / RF-11, task 6.3).

Transcripts and audio are the only on-disk artifacts the assistant produces;
they live under ``config.LOGS_DIR`` (capture/ and reply/ wavs plus
transcripts.jsonl) and are deletable on demand with ``jarvis clean``. State
(RF-6 active project + the RF-11 off switch) and config are deliberately NOT
logs: ``clean_logs`` never touches anything outside the logs directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_SECRET_KEYS = {"access_token", "refresh_token", "authorization_code", "code", "state", "verifier", "client_secret"}
_SECRET_PARAM = re.compile(r"(?i)(access_token|refresh_token|authorization_code|code|state|verifier|client_secret)=([^&\s]+)")


def redact_text(value: str) -> str:
    """Remove OAuth material while retaining safe diagnostic context."""
    return _SECRET_PARAM.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)


def redact_entities(value: object) -> object:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if str(key).casefold() in _SECRET_KEYS else redact_entities(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_entities(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


class TranscriptLog:
    """Appends one JSON line per handled utterance to a transcripts journal."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def record(
        self,
        transcript: str,
        intent: str | None = None,
        outcome: str | None = None,
        entities: dict | None = None,
    ) -> None:
        if not transcript:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "transcript": redact_text(transcript),
            "intent": intent,
            "outcome": outcome,
            "entities": redact_entities(entities),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def clean_logs(logs_dir: Path | str) -> int:
    """Delete every generated log file under ``logs_dir``; returns the count.

    Only the logs directory is touched — state.json and config live outside it
    and are preserved (a clean must not reset the RF-11 off switch or the
    RF-6 active project). Empty directories are left in place.
    """
    root = Path(logs_dir)
    if not root.is_dir():
        return 0
    deleted = 0
    for path in root.rglob("*"):
        if path.is_file():
            path.unlink()
            deleted += 1
    return deleted
