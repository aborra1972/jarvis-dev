"""Shared pytest fixtures (bootstrap skeleton).

Later PRs extend this file with the fakes the design's testing strategy needs
(injectable clock, fake subprocess/transport, fake executor registry).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Pin the assistant persona BEFORE config.py's _load_env() reads the repo-root
# .env: the whole suite assumes the jarvis defaults (ANNOUNCEMENT, spoken
# fallbacks, voices), so a leftover JARVIS_AGENT=... in .env (e.g. after a
# manual `jarvis agent friday`) must never leak into a test run. _load_env
# refuses to overwrite existing env vars, so this pin wins.
os.environ["JARVIS_AGENT"] = "jarvis"

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to ``tests/fixtures`` (rioplatense corpus, sample wavs, M3 proxy)."""
    return _FIXTURES
