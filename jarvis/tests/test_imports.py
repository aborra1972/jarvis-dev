"""Bootstrap smoke tests (PR1).

Verifies the skeleton contract: every package module imports, stub callables
fail loudly (NotImplementedError) until their PR lands, the CLI surfaces the
six lifecycle commands, and config exposes the wired spike paths/ports.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

import pytest

import jarvis
import jarvis.cli
import jarvis.config

# Every skeleton module must import (design Repo Structure).
SKELETON_MODULES = (
    "jarvis",
    "jarvis.audio",
    "jarvis.audio.capture",
    "jarvis.audio.wake",
    "jarvis.audio.stt",
    "jarvis.audio.tts",
    "jarvis.audio.playback",
    "jarvis.audio.pipeline",
    "jarvis.cli",
    "jarvis.config",
    "jarvis.cli",
    "jarvis.config",
    "jarvis.interpreter",
    "jarvis.interpreter.normalize",
    "jarvis.interpreter.golden",
    "jarvis.interpreter.llm",
    "jarvis.interpreter.schema",
    "jarvis.orchestrator",
    "jarvis.orchestrator.state",
    "jarvis.orchestrator.confirm",
    "jarvis.orchestrator.session",
    "jarvis.orchestrator.supervisor",
    "jarvis.orchestrator.loop",
    "jarvis.actions",
    "jarvis.actions.base",
    "jarvis.actions.opencode",
    "jarvis.actions.system",
    "jarvis.actions.files",
    "jarvis.actions.web",
    "jarvis.actions.assistant_lifecycle",
)

# Stub callables must raise until their PR lands (fail loud, no fake logic).
# NOTE (PR2): the four interpreter stubs were implemented in PR2 and their
# stub entries removed — behavior is covered by tests/unit/test_normalize.py,
# test_golden.py, test_schema.py, test_llm.py, test_interpreter.py.
# NOTE (PR3): the orchestrator stubs (state, confirm, session, supervisor,
# loop) were implemented in PR3 and removed — covered by tests/unit/test_state.py,
# test_confirm.py, test_session.py, test_supervisor.py, test_loop.py.
# NOTE (PR5): the voice stubs (audio, wake, stt, tts) all landed in the audio
# package — no stub callables remain, so test_stub_fails_until_logic_lands was
# removed too.

CLI_COMMANDS = ("start", "stop", "off", "on", "clean", "logs")
# Wired in PR3 (start/off/on) or task 6.3 (clean); stop/logs stay skeleton.
CLI_STUBS = ("stop", "logs")


# --- Package -----------------------------------------------------------------
def test_package_version() -> None:
    assert isinstance(jarvis.__version__, str)
    assert jarvis.__version__


@pytest.mark.parametrize("module", SKELETON_MODULES)
def test_skeleton_module_imports(module: str) -> None:
    importlib.import_module(module)


# --- CLI ---------------------------------------------------------------------
def test_cli_parser_exposes_lifecycle_commands() -> None:
    parser = jarvis.cli.build_parser()
    assert isinstance(parser, argparse.ArgumentParser)
    subparsers = {a.dest: a for a in parser._actions if isinstance(a, argparse._SubParsersAction)}
    actions = subparsers["command"].choices
    assert set(actions) == set(CLI_COMMANDS)


@pytest.mark.parametrize("cmd", CLI_STUBS)
def test_cli_subcommand_is_a_stub(cmd: str, capsys: pytest.CaptureFixture) -> None:
    assert jarvis.cli.main([cmd]) == 1
    assert "not implemented yet" in capsys.readouterr().err


def test_cli_start_runs_real_pipeline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(jarvis.config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(jarvis.config, "RUN_DIR", tmp_path / "run")
    monkeypatch.setattr(jarvis.config, "PID_FILE", tmp_path / "run" / "jarvis.pid")
    ran: list[object] = []
    monkeypatch.setattr(jarvis.orchestrator.loop, "run", lambda pipeline, iterations=None: ran.append(pipeline))

    class _FakeSpeaker:
        def __init__(self) -> None:
            self.spoken: list[str] = []

        def speak(self, text: str) -> None:
            self.spoken.append(text)

        def flush(self) -> None:
            pass

    fake = _FakeSpeaker()
    monkeypatch.setattr(jarvis.orchestrator.loop, "PiperSpeaker", lambda *a, **k: fake)
    # Real adapter wiring (sounddevice/OpenWakeWord/whisper/piper) is covered by
    # test_bootstrap with recorders; here only the start() flow must run fast
    # and without loading ONNX/hardware.
    monkeypatch.setattr(jarvis.orchestrator.loop, "build_wake_detector", lambda *a, **k: None)
    monkeypatch.setattr(jarvis.orchestrator.loop, "SoundDeviceCapturer", lambda *a, **k: None)
    monkeypatch.setattr(jarvis.orchestrator.loop, "MicSwitch", lambda *a, **k: (lambda: False))

    signals: list[object] = []
    monkeypatch.setattr(
        jarvis.orchestrator.loop,
        "_register_switch_signals",
        lambda session, switch, speaker=None: signals.append((session, switch)),
    )

    assert jarvis.cli.main(["start"]) == 0
    assert ran and ran[0].speaker is fake
    assert signals, "start() must wire the RF-11 non-vocal signal handlers"
    assert not (tmp_path / "run" / "jarvis.pid").exists()  # pid removed on exit
    assert fake.spoken == ["Buen día, señor. Soy Jarvis, a su servicio."]
    assert "skeleton" not in capsys.readouterr().err


def test_cli_off_sets_switch_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(jarvis.config, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(jarvis.config, "PID_FILE", tmp_path / "jarvis.pid")
    assert jarvis.cli.main(["off"]) == 0
    assert (tmp_path / "state.json").exists()
    assert capsys.readouterr().err  # non-silent switch feedback
    assert jarvis.cli.main(["on"]) == 0


def test_cli_clean_deletes_logs_and_confirms(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(jarvis.config, "LOGS_DIR", tmp_path / "logs")
    (tmp_path / "logs" / "capture").mkdir(parents=True)
    (tmp_path / "logs" / "capture" / "utterance.wav").write_bytes(b"wav")
    assert jarvis.cli.main(["clean"]) == 0
    assert "eliminados" in capsys.readouterr().err
    assert not (tmp_path / "logs" / "capture" / "utterance.wav").exists()


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        jarvis.cli.build_parser().parse_args(["--help"])
    assert exc.value.code == 0


def test_cli_no_args_prints_help_and_exits_zero(capsys: pytest.CaptureFixture) -> None:
    assert jarvis.cli.main([]) == 0
    assert "jarvis" in capsys.readouterr().out


# --- Config ------------------------------------------------------------------
def test_config_wires_spike_artifacts() -> None:
    for attr in ("SPIKE", "WHISPER_CLI", "WHISPER_MODEL", "PIPER_BIN", "PIPER_MODEL", "PIPER_CONFIG"):
        assert isinstance(getattr(jarvis.config, attr), Path)


def test_config_wires_voice_pipeline() -> None:
    assert jarvis.config.WHISPER_MODEL_MEDIUM.is_file()
    assert jarvis.config.WHISPER_MODEL.is_file()
    assert isinstance(jarvis.config.WHISPER_PROMPT, str) and jarvis.config.WHISPER_PROMPT
    assert isinstance(jarvis.config.WAKE_THRESHOLD, float)
    assert isinstance(jarvis.config.WAKE_VAD_THRESHOLD, float)
    assert jarvis.config.AUDIO_SAMPLE_RATE == 16000
    assert isinstance(jarvis.config.AUDIO_SILENCE_MS, int)
    assert jarvis.config.STT_TIMEOUT_S > 0
    assert jarvis.config.STT_GATE_DURATION_S > 0
    assert jarvis.config.TTS_TIMEOUT_S > 0
    assert jarvis.config.PLAY_TIMEOUT_S > 0
    assert isinstance(jarvis.config.PLAYER_BIN, str) and jarvis.config.PLAYER_BIN


def test_config_wires_pr6_voice_settings() -> None:
    assert isinstance(jarvis.config.WHISPER_BEAM, int) and jarvis.config.WHISPER_BEAM >= 1
    assert isinstance(jarvis.config.STT_MEDIUM_PROMOTED, bool)
    assert jarvis.config.WHISPER_VAD_MODEL is None or isinstance(
        jarvis.config.WHISPER_VAD_MODEL, Path
    )
    assert jarvis.config.WAKE_CUSTOM_MODEL is None or isinstance(
        jarvis.config.WAKE_CUSTOM_MODEL, Path
    )


def test_config_wires_server_ports() -> None:
    assert jarvis.config.OPCODE_HOST == "127.0.0.1"
    assert isinstance(jarvis.config.OPCODE_BASE_PORT, int)
    assert jarvis.config.OPCODE_BASE_PORT > 0
    assert isinstance(jarvis.config.STATE_FILE, Path)


def test_config_wires_allowlists_and_prompt_placeholders() -> None:
    assert isinstance(jarvis.config.ALLOWED_APPS, set)
    assert isinstance(jarvis.config.INTERPRETER_SYSTEM_PROMPT, str)


# --- Fixtures -----------------------------------------------------------------
def test_fixtures_dir_fixture(fixtures_dir: Path) -> None:
    assert fixtures_dir.name == "fixtures"
    assert fixtures_dir.is_dir()
