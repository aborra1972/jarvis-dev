"""Assistant lifecycle executors (PR4, task 4.7): power_off_self, help.

Design (binding: single location): power_off_self lives ONLY here and is
golden-gated + 15s-confirmed by the orchestrator; the executor only logs and
acknowledges. handle_help enumerates the 15-command allowlist.
"""

from __future__ import annotations

import json
import urllib.request

from jarvis.actions import assistant_lifecycle, base
from jarvis.interpreter.schema import ALLOWED_INTENTS, Intent


def _intent(name, entities=None, **overrides):
    kwargs = {"intent": name, "entities": entities or {}, "confidence": 0.9}
    kwargs.update(overrides)
    return Intent(**kwargs)


def test_power_off_self_logs_and_acknowledges(monkeypatch) -> None:
    logged = []
    monkeypatch.setattr(assistant_lifecycle.base, "log", lambda event: logged.append(event))
    result = assistant_lifecycle.power_off_self(_intent("power_off_self"), None)
    assert result.ok is True
    assert logged == ["power_off_self"]


def test_handle_help_lists_all_commands(monkeypatch) -> None:
    result = assistant_lifecycle.handle_help(_intent("help"), None)
    assert result.ok is True
    for command in ALLOWED_INTENTS - {"unknown"}:
        assert command in result.spoken


class _FakeJsonResponse:
    """Minimal urllib response: JSON body, context-manager protocol."""

    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeJsonResponse":
        return self

    def __exit__(self, *exc) -> bool:
        return False


def test_general_qa_uses_agent_personality_as_system_prompt(monkeypatch) -> None:
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeJsonResponse(b'{"response": "respuesta de prueba"}')

    monkeypatch.setenv("JARVIS_AGENT", "karen")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = assistant_lifecycle.handle_general_qa(
        _intent("general_qa", {"query": "¿qué hora es?"}), None
    )
    assert result.ok is True
    assert result.spoken == "respuesta de prueba"
    assert "Karen" in captured["body"]["system"]
    assert "amigo" in captured["body"]["system"]


def test_handle_weather_returns_action_result_with_deterministic_service() -> None:
    class FakeWeatherService:
        def current(self, location):
            assert location == "CABA, Argentina"
            return type("Reading", (), {
                "location": "Buenos Aires, Argentina",
                "temperature_c": 22.0,
                "weather_code": 0,
            })()

    result = assistant_lifecycle.handle_weather(
        _intent("general_qa", {"weather_location": "CABA, Argentina", "weather_ambiguous": "false"}),
        None,
        service=FakeWeatherService(),
    )

    assert isinstance(result, assistant_lifecycle.ActionResult)
    assert result.ok is True
    assert result.spoken == "En Buenos Aires, Argentina hay 22 grados y está despejado."


def test_codex_combined_answer_is_used_without_a_second_call(monkeypatch) -> None:
    monkeypatch.setattr(assistant_lifecycle.config, "LLM_PROVIDER", "codex")
    result = assistant_lifecycle.handle_general_qa(
        _intent("general_qa", {"query": "hola"}), None,
        answer="Respuesta combinada.", combined=True,
    )
    assert result.ok is True
    assert result.spoken == "Respuesta combinada."


def test_codex_combined_missing_answer_falls_back_without_call(monkeypatch) -> None:
    monkeypatch.setattr(assistant_lifecycle.config, "LLM_PROVIDER", "codex")
    result = assistant_lifecycle.handle_general_qa(
        _intent("general_qa", {"query": "hola"}), None, combined=True,
    )
    assert result.ok is True
    assert "No tengo una respuesta" in result.spoken


def test_general_qa_empty_query_uses_agent_address(monkeypatch) -> None:
    monkeypatch.setenv("JARVIS_AGENT", "friday")
    result = assistant_lifecycle.handle_general_qa(_intent("general_qa", {}), None)
    assert result.ok is False
    assert result.spoken == "No recibí la pregunta, jefe."


def test_stream_general_qa_uses_agent_personality_as_system_prompt(
    monkeypatch,
) -> None:
    captured: dict = {}
    spoken: list[str] = []

    class _Stream:
        def __enter__(self) -> "_Stream":
            return self

        def __exit__(self, *exc) -> bool:
            return False

        def __iter__(self):
            yield b'{"response": "Hola, jefe.", "done": false}\n'
            yield b'{"response": " Listo.", "done": true}\n'

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _Stream()

    monkeypatch.setenv("JARVIS_AGENT", "friday")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    result = assistant_lifecycle.stream_general_qa(
        _intent("general_qa", {"query": "hola"}), None, spoken.append
    )
    assert result.ok is True
    assert result.data["response"] == "Hola, jefe. Listo."
    assert "Friday" in captured["body"]["system"]
    assert "jefe" in captured["body"]["system"]
    assert spoken == ["Hola, jefe.", "Listo."]  # sentence split consumes the space
