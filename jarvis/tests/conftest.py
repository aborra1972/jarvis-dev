"""Shared pytest fixtures (bootstrap skeleton).

Later PRs extend this file with the fakes the design's testing strategy needs
(injectable clock, fake subprocess/transport, fake executor registry).
"""

from __future__ import annotations

from pathlib import Path

import pytest

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to ``tests/fixtures`` (rioplatense corpus, sample wavs, M3 proxy)."""
    return _FIXTURES
