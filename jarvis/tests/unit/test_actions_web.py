"""Web executors (PR4, task 4.6): web_search via google, open_url validated.

Design (RF-10, threat matrix): search/URL actions only spawn xdg-open with a
validated http(s) URL (malformed URL ⇒ rejected, nothing spawned); the search
engine is allowlisted (google only). No shell, list-args only.
"""

from __future__ import annotations

from jarvis.actions import web
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


def _commands(monkeypatch):
    commands = []
    monkeypatch.setattr(
        web.base,
        "safe_run",
        lambda command, timeout=20.0: commands.append(command) or (0, ""),
    )
    return commands


# --- build_search_url ----------------------------------------------------------
def test_build_search_url_encodes_query() -> None:
    url = web.build_search_url("hola mundo & amigos", "google")
    assert url.startswith("https://www.google.com/search?")
    assert "q=hola+mundo+%26+amigos" in url


def test_build_search_url_rejects_unknown_engine() -> None:
    assert web.build_search_url("hola", "bing") is None


# --- web_search -----------------------------------------------------------------
def test_web_search_spawns_xdg_open_with_google_url(monkeypatch) -> None:
    commands = _commands(monkeypatch)
    result = web.web_search(_intent("web_search", {"query": "clima hoy"}), None)
    assert result.ok is True
    assert commands[0][0] == "xdg-open"
    assert commands[0][1].startswith("https://www.google.com/search?q=")


def test_web_search_unknown_engine_is_rejected(monkeypatch) -> None:
    commands = _commands(monkeypatch)
    result = web.web_search(_intent("web_search", {"query": "x", "engine": "bing"}), None)
    assert result.ok is False
    assert commands == []


# --- open_url --------------------------------------------------------------------
def test_open_url_spawns_xdg_open_with_http_url(monkeypatch) -> None:
    commands = _commands(monkeypatch)
    result = web.open_url(_intent("open_url", {"url": "https://example.com/a?b=1"}), None)
    assert result.ok is True
    assert commands == [["xdg-open", "https://example.com/a?b=1"]]


def test_open_url_malformed_is_rejected_and_never_spawns(monkeypatch) -> None:
    commands = _commands(monkeypatch)
    result = web.open_url(_intent("open_url", {"url": "ftp://example.com"}), None)
    assert result.ok is False
    assert commands == []


def test_open_url_non_http_is_rejected(monkeypatch) -> None:
    commands = _commands(monkeypatch)
    result = web.open_url(_intent("open_url", {"url": "file:///etc/passwd"}), None)
    assert result.ok is False
    assert commands == []
