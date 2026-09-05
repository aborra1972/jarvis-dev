"""CLI ``jarvis agent`` / ``jarvis setup`` (selector de agente/personaje).

These write JARVIS_AGENT=<agent> into the repo-root .env (config.ENV_FILE),
preserving every other key; tests redirect ENV_FILE to tmp_path so the real
repo .env is never touched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis import cli, config


def _redirect_env_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    env_path = tmp_path / ".env"
    monkeypatch.setattr(config, "ENV_FILE", env_path)
    return env_path


def test_agent_without_args_prints_active_agent(capsys: pytest.CaptureFixture) -> None:
    assert cli.main(["agent"]) == 0
    out = capsys.readouterr().out
    assert config.AGENT in out
    assert config.AGENT_PROFILES[config.AGENT]["name"] in out
    assert config.EDGE_VOICE in out


def test_agent_set_writes_env_and_preserves_other_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    env_path.write_text("# comentario\nGEMINI_API_KEY=abc123\n")
    assert cli.main(["agent", "friday"]) == 0
    out = capsys.readouterr().out
    assert "Friday" in out
    assert "reiniciar" in out
    lines = env_path.read_text()
    assert "JARVIS_AGENT=friday" in lines
    assert "GEMINI_API_KEY=abc123" in lines
    assert "# comentario" in lines


def test_agent_set_accepts_case_insensitive_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    assert cli.main(["agent", "KAREN"]) == 0
    assert "JARVIS_AGENT=karen" in env_path.read_text()


def test_agent_set_replaces_existing_jarvivs_agent_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    env_path.write_text("JARVIS_AGENT=friday\n")
    assert cli.main(["agent", "jarvis"]) == 0
    lines = env_path.read_text()
    assert "JARVIS_AGENT=jarvis" in lines
    assert "JARVIS_AGENT=friday" not in lines


def test_agent_set_invalid_name_rejects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    assert cli.main(["agent", "terminator"]) == 1
    assert "agente desconocido" in capsys.readouterr().err
    assert not env_path.exists() or "JARVIS_AGENT" not in env_path.read_text()


def test_setup_with_name_is_non_interactive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    assert cli.main(["setup", "karen"]) == 0
    assert "Karen" in capsys.readouterr().out
    assert "JARVIS_AGENT=karen" in env_path.read_text()


def test_setup_interactive_choice_writes_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")  # 2 = friday
    assert cli.main(["setup"]) == 0
    assert "JARVIS_AGENT=friday" in env_path.read_text()


def test_setup_cancel_keeps_env_untouched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    env_path = _redirect_env_file(monkeypatch, tmp_path)
    env_path.write_text("GEMINI_API_KEY=abc\n")
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    assert cli.main(["setup"]) == 0
    assert "GEMINI_API_KEY=abc" in env_path.read_text()
    assert "JARVIS_AGENT" not in env_path.read_text()
    assert "cancelado" in capsys.readouterr().out