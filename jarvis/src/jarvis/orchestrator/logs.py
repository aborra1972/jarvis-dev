"""Local deletable logs (RNF-3 / RF-11, task 6.3).

Transcripts and audio are the only on-disk artifacts the assistant produces;
they live under ``config.LOGS_DIR`` (capture/ and reply/ wavs plus
transcripts.jsonl) and are deletable on demand with ``jarvis clean``. State
(RF-6 active project + the RF-11 off switch) and config are deliberately NOT
logs: ``clean_logs`` never touches anything outside the logs directory.
"""

from __future__ import annotations

import json
from pathlib import Path


class TranscriptLog:
    """Appends one JSON line per handled utterance to a transcripts journal."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def record(self, transcript: str, intent: str | None = None, outcome: str | None = None) -> None:
        if not transcript:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"transcript": transcript, "intent": intent, "outcome": outcome}
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
