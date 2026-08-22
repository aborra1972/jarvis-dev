"""Tests for jarvis.diagnose module."""

from __future__ import annotations

import subprocess
from unittest.mock import patch, MagicMock

from jarvis import diagnose


class TestDiagResult:
    """Tests for DiagResult display."""

    def test_pass_result(self):
        r = diagnose.DiagResult("Mic", True, "found device")
        text = str(r)
        assert "\u2705" in text  # checkmark
        assert "Mic" in text
        assert "found device" in text

    def test_fail_result_with_hint(self):
        r = diagnose.DiagResult("Mic", False, "not found", "install alsa-utils")
        text = str(r)
        assert "\u274c" in text  # cross
        assert "Mic" in text
        assert "not found" in text
        assert "install alsa-utils" in text

    def test_fail_result_no_hint(self):
        r = diagnose.DiagResult("Mic", False, "not found")
        text = str(r)
        assert "\u274c" in text
        assert "->" not in text


class TestCheckMicrophone:
    """Tests for microphone detection."""

    @patch("jarvis.diagnose._run")
    def test_mic_found(self, mock_run):
        mock_run.return_value = (0, "card 0: PCH [HDA Intel PCH], device 0: ALC887-VD Analog", "")
        r = diagnose.check_microphone()
        assert r.ok is True
        assert "HDA Intel PCH" in r.message

    @patch("jarvis.diagnose._run")
    def test_mic_not_found(self, mock_run):
        mock_run.return_value = (1, "", "no devices")
        r = diagnose.check_microphone()
        assert r.ok is False

    @patch("jarvis.diagnose._run")
    def test_arecord_not_installed(self, mock_run):
        mock_run.return_value = (-1, "", "command not found")
        r = diagnose.check_microphone()
        assert r.ok is False
        assert "alsa-utils" in r.hint


class TestCheckWhisper:
    """Tests for whisper CLI + model detection."""

    @patch("jarvis.diagnose.config")
    @patch("pathlib.Path.exists")
    def test_whisper_ok(self, mock_exists, mock_config):
        mock_exists.return_value = True
        mock_config.WHISPER_CLI = MagicMock()
        mock_config.WHISPER_CLI.exists.return_value = True
        mock_config.WHISPER_MODEL = MagicMock()
        mock_config.WHISPER_MODEL.stat.return_value = MagicMock(st_size=487 * 1024 * 1024)
        mock_config.WHISPER_MODEL.name = "ggml-small.bin"
        mock_config.STT_USE_TINY = False

        r = diagnose.check_whisper()
        assert r.ok is True

    @patch("jarvis.diagnose.config")
    def test_whisper_cli_missing(self, mock_config):
        mock_config.WHISPER_CLI = MagicMock()
        mock_config.WHISPER_CLI.exists.return_value = False
        mock_config.WHISPER_MODEL = MagicMock()
        mock_config.WHISPER_MODEL.exists.return_value = True
        mock_config.STT_USE_TINY = False

        r = diagnose.check_whisper()
        assert r.ok is False


class TestCheckOllama:
    """Tests for Ollama server detection."""

    @patch("jarvis.diagnose._run")
    @patch("jarvis.diagnose.config")
    def test_ollama_running_with_model(self, mock_config, mock_run):
        mock_config.INTERPRETER_LLM_MODEL = "qwen2.5:3b"
        mock_run.return_value = (0, "NAME          ID\nqwen2.5:3b    abc123", "")
        r = diagnose.check_ollama()
        assert r.ok is True

    @patch("jarvis.diagnose._run")
    @patch("jarvis.diagnose.config")
    def test_ollama_not_running(self, mock_config, mock_run):
        mock_config.INTERPRETER_LLM_MODEL = "qwen2.5:3b"
        mock_run.return_value = (-1, "", "command not found")
        r = diagnose.check_ollama()
        assert r.ok is False
        assert "ollama serve" in r.hint

    @patch("jarvis.diagnose._run")
    @patch("jarvis.diagnose.config")
    def test_ollama_running_missing_model(self, mock_config, mock_run):
        mock_config.INTERPRETER_LLM_MODEL = "qwen2.5:3b"
        mock_run.return_value = (0, "NAME          ID\nllama3.2      def456", "")
        r = diagnose.check_ollama()
        assert r.ok is False
        assert "ollama pull" in r.hint


class TestCheckAudioOutput:
    """Tests for audio output detection."""

    @patch("jarvis.diagnose.shutil.which")
    @patch("jarvis.diagnose._run")
    def test_audio_ok_pulseaudio(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/paplay"
        mock_run.return_value = (0, "Server Name: pulseaudio", "")
        r = diagnose.check_audio_output()
        assert r.ok is True

    @patch("jarvis.diagnose.shutil.which")
    def test_player_not_installed(self, mock_which):
        mock_which.return_value = None
        r = diagnose.check_audio_output()
        assert r.ok is False


class TestRunAll:
    """Tests for run_all() integration."""

    @patch("jarvis.diagnose.check_microphone")
    @patch("jarvis.diagnose.check_wake_word")
    @patch("jarvis.diagnose.check_whisper")
    @patch("jarvis.diagnose.check_piper")
    @patch("jarvis.diagnose.check_ollama")
    @patch("jarvis.diagnose.check_audio_output")
    def test_all_pass(self, *mocks):
        for m in mocks:
            m.return_value = diagnose.DiagResult(m.__name__, True, "ok")
        results = diagnose.run_all()
        assert len(results) == 6
        assert all(r.ok for r in results)

    @patch("jarvis.diagnose.check_ollama")
    @patch("jarvis.diagnose.check_microphone")
    def test_partial_failure(self, mock_mic, mock_ollama):
        # Only test a subset to avoid mocking everything
        mock_mic.return_value = diagnose.DiagResult("Mic", False, "not found")
        mock_ollama.return_value = diagnose.DiagResult("Ollama", True, "ok")


class TestMain:
    """Tests for main() exit codes."""

    @patch("jarvis.diagnose.run_all")
    def test_main_returns_0_when_all_ok(self, mock_run_all, capsys):
        mock_run_all.return_value = [
            diagnose.DiagResult("A", True, "ok"),
            diagnose.DiagResult("B", True, "ok"),
        ]
        rc = diagnose.main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "2/2 componentes OK" in out

    @patch("jarvis.diagnose.run_all")
    def test_main_returns_1_when_failures(self, mock_run_all, capsys):
        mock_run_all.return_value = [
            diagnose.DiagResult("A", True, "ok"),
            diagnose.DiagResult("B", False, "fail", "fix it"),
        ]
        rc = diagnose.main()
        assert rc == 1
        out = capsys.readouterr().out
        assert "1/2 componentes OK" in out
