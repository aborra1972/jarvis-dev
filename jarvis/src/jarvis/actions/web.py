"""Web executor (bootstrap skeleton).

Design: web_search and open_url via xdg-open, URL validated as http/https
(RF-10); no partial execution on failure. Real implementation lands in PR4
(executors).
"""

from __future__ import annotations


def open_url() -> None:
    """Bootstrap stub — real implementation lands in PR4 (executors)."""
    raise NotImplementedError("jarvis.actions.web.open_url: implemented in PR4 (executors)")
