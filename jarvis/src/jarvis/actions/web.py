"""Web executor (PR4, task 4.6): web_search via google, open_url validated.

Design (RF-10, threat matrix): search/URL actions only spawn xdg-open with a
validated http(s) URL (malformed URL => rejected, nothing spawned); the search
engine is allowlisted (google only). All subprocess is list-args via
base.safe_run (no shell).
"""

from __future__ import annotations

from urllib.parse import urlencode

from jarvis.actions import base
from jarvis.interpreter import schema
from jarvis.interpreter.schema import Intent
from jarvis.orchestrator.contracts import ActionResult

_ENGINES = {"google": "https://www.google.com/search"}


def build_search_url(query: str, engine: str = "google") -> str | None:
    """Build a search URL for an allowlisted engine; None for unknown engines."""
    base_url = _ENGINES.get(engine)
    if base_url is None:
        return None
    return f"{base_url}?{urlencode({'q': query})}"


def web_search(intent: Intent, session: object) -> ActionResult:
    query = intent.entities.get("query", "").strip()
    engine = intent.entities.get("engine", "google").strip() or "google"
    url = build_search_url(query, engine)
    if url is None:
        return ActionResult(ok=False, spoken="No conozco ese buscador, señor.")
    code, _ = base.safe_run(["xdg-open", url])
    if code != 0:
        return ActionResult(ok=False, spoken="Lo lamento, señor, no pude buscar eso.")
    return ActionResult(ok=True, spoken=f"Buscando {query}, señor.")


def open_url(intent: Intent, session: object) -> ActionResult:
    url = intent.entities.get("url", "").strip()
    if schema.validate_entities(intent):
        return ActionResult(ok=False, spoken="No puedo abrir esa dirección, señor.")
    code, _ = base.safe_run(["xdg-open", url])
    if code != 0:
        return ActionResult(ok=False, spoken="Lo lamento, señor, no pude abrir esa dirección.")
    return ActionResult(ok=True, spoken="Abriendo la página, señor.")
