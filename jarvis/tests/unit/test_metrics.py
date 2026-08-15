"""Task 6.3 WU3: verification of PRD success metrics M4/M5/M6.

Turns the PRD's success metrics into executable checks (no invented metrics):
- M6 (100% confirmations): every destructive intent is golden-gated with
  ``confirm_required=True``, no fast-path can emit one, and each has a verbal
  confirmation prompt.
- M4 (no regression of flow): an OpenCode failure degrades to a spoken notice
  (never a crash) and system actions keep working.
- M5 (domain coverage): one representative intent per domain (opencode,
  system, files, web) executes through the real registry without blocking
  errors.

Supporting evidence lives in the per-executor unit tests and the e2e suite
(real spike binaries); these checks are the aggregate MVP-vs-metric gate.
"""

from __future__ import annotations

from pathlib import Path

from jarvis import config
from jarvis.actions import base
from jarvis.actions.opencode import OFFLINE_SPOKEN
from jarvis.interpreter.golden import DESTRUCTIVE_PATTERNS, FAST_PATH_PATTERNS, gate
from jarvis.interpreter.schema import DESTRUCTIVE_INTENTS, Intent
from jarvis.orchestrator.confirm import confirmation_prompt
from jarvis.orchestrator.session import Session


# --- M6: 100% of destructive actions are confirmed before execution ----------
def test_m6_golden_destructive_matches_always_require_confirmation() -> None:
    samples = {
        "shutdown": "cerrar linux",
        "reboot": "reiniciar la maquina",
        "power_off_self": "apagarse",
    }
    for intent_name, phrase in samples.items():
        intent = gate(phrase)
        assert intent is not None, f"{phrase!r} must hit the golden gate"
        assert intent.intent == intent_name
        assert intent.confirm_required is True


def test_m6_no_fast_path_emits_destructive_intent() -> None:
    fast_intents = {intent for _, intent, _ in FAST_PATH_PATTERNS}
    assert fast_intents.isdisjoint(DESTRUCTIVE_INTENTS)


def test_m6_every_destructive_intent_has_verbal_confirmation_prompt() -> None:
    for intent_name in DESTRUCTIVE_INTENTS:
        prompt = confirmation_prompt(Intent(intent=intent_name))
        assert prompt, f"{intent_name} must have a confirmation prompt"
        assert "confirm" in prompt.lower()


def test_m6_destructive_gate_is_authoritative_over_llm() -> None:
    # An LLM may never emit a destructive intent without confirm_required;
    # the golden gate is the only source that sets it (ADR-2). Sanity check:
    # a destructive surface with confirm_required=False must be impossible.
    intent = gate("cerrar linux")
    assert intent is not None and intent.confirm_required is True
    assert intent.source == "golden"


# --- M4: user keeps using OpenCode normally if Jarvis fails ------------------
def test_m4_opencode_degrades_to_spoken_notice_and_system_still_works(
    tmp_path: Path, monkeypatch
) -> None:
    class _DeadManager:
        def ensure_server(self, port, path) -> bool:
            return False

    monkeypatch.setattr(
        "jarvis.actions.opencode.ServerManager", lambda *a, **k: _DeadManager()
    )
    registry = base.build_registry()
    session = Session(active_project=str(tmp_path))

    open_result = registry.execute(
        Intent(intent="open_repo", entities={"repo": str(tmp_path)}, confidence=0.9),
        session,
    )

    assert open_result.ok is False
    assert open_result.spoken == OFFLINE_SPOKEN

    monkeypatch.setattr(base, "safe_run", lambda command, timeout=20.0: (0, ""))
    app_result = registry.execute(
        Intent(intent="open_app", entities={"app": "firefox"}, confidence=0.9), session
    )
    assert app_result.ok is True
    assert "abriendo" in app_result.spoken


# --- M5: the 4 action domains work without blocking errors -------------------
def test_m5_all_four_domains_execute_without_blocking_errors(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(base, "safe_run", lambda command, timeout=20.0: (0, ""))

    class _HealthyManager:
        def ensure_server(self, port, path) -> bool:
            return True

    monkeypatch.setattr(
        "jarvis.actions.opencode.ServerManager", lambda *a, **k: _HealthyManager()
    )
    registry = base.build_registry()
    session = Session(active_project=str(tmp_path))

    cases = {
        "opencode": Intent(intent="open_repo", entities={"repo": str(tmp_path)}, confidence=0.9),
        "system": Intent(intent="open_app", entities={"app": "firefox"}, confidence=0.9),
        "files": Intent(intent="create_doc", entities={"text": "resumen del sprint"}, confidence=0.9),
        "web": Intent(intent="open_url", entities={"url": "https://example.com"}, confidence=0.9),
    }
    for domain, intent in cases.items():
        result = registry.execute(intent, session)
        assert result.ok is True, f"{domain} must execute without blocking errors: {result.spoken}"
