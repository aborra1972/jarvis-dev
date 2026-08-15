"""Speech-to-text tests (PR5, task 5.3).

Design ADR-4: whisper-cli subprocess wrapper (no shell) with `-l es -b 1 --vad
--prompt <domain>`, 15s timeout. The wrapper picks the model by estimated
utterance duration — the q5-medium gate (≤4s) — falling back to the small
model for longer utterances. Tests run against a fake whisper-cli script in a
tmp dir: no real model, no hardware.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.audio.stt import STTError, WhisperSTT, select_model

FIXTURE_PROMPT = "asistente de desarrollo, comandos y web"


@pytest.fixture
def fake_whisper_cli(tmp_path: Path) -> Path:
    """A fake whisper-cli that echoes a fixed transcript and logs its args."""
    script = tmp_path / "whisper-cli"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "log = open(sys.argv[0] + '.log', 'w')\n"
        "json.dump(sys.argv[1:], log)\n"
        "log.close()\n"
        "print('cambia el volumen al cincuenta por ciento')\n"
    )
    script.chmod(0o755)
    return script


# --- Model gate by duration ---------------------------------------------------
def test_select_model_uses_medium_within_gate() -> None:
    small = Path("/models/small.bin")
    medium = Path("/models/medium.bin")
    assert select_model(2.0, small, medium) == medium
    assert select_model(4.0, small, medium) == medium


def test_select_model_falls_back_to_small_beyond_gate() -> None:
    small = Path("/models/small.bin")
    medium = Path("/models/medium.bin")
    assert select_model(4.5, small, medium) == small
    assert select_model(10.0, small, medium) == small


def test_select_model_without_medium_always_small() -> None:
    small = Path("/models/small.bin")
    assert select_model(1.0, small, None) == small


# --- WhisperSTT.transcribe ----------------------------------------------------
def test_transcribe_builds_list_args_command(
    fake_whisper_cli: Path, tmp_path: Path
) -> None:
    stt = WhisperSTT(
        whisper_cli=fake_whisper_cli,
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
    )
    wav = tmp_path / "u.wav"
    wav.write_bytes(b"RIFF")

    assert stt.transcribe(wav, duration_s=1.0) == "cambia el volumen al cincuenta por ciento"

    args = eval((fake_whisper_cli.parent / (fake_whisper_cli.name + ".log")).read_text())
    assert args[0] == "-m"
    assert args[1].endswith("medium.bin")
    assert args[2] == "-f"
    assert args[3] == str(wav)
    assert "-l" in args and "es" in args
    # PR6 (integration): whisper.cpp 1.9.x names beam size `-bs`, not `-b`.
    assert "-bs" in args and "1" in args
    assert "--prompt" in args and FIXTURE_PROMPT in args


def test_transcribe_omits_vad_when_no_vad_model(
    fake_whisper_cli: Path, tmp_path: Path
) -> None:
    stt = WhisperSTT(
        whisper_cli=fake_whisper_cli,
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
        vad_model=None,
    )
    wav = tmp_path / "u.wav"
    wav.write_bytes(b"RIFF")
    stt.transcribe(wav, duration_s=1.0)
    args = eval((fake_whisper_cli.parent / (fake_whisper_cli.name + ".log")).read_text())
    assert "--vad" not in args
    assert "-vm" not in args


def test_transcribe_adds_vad_with_vad_model(
    fake_whisper_cli: Path, tmp_path: Path
) -> None:
    vad_model = tmp_path / "silero.ggml.bin"
    vad_model.write_bytes(b"vad")
    stt = WhisperSTT(
        whisper_cli=fake_whisper_cli,
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
        vad_model=vad_model,
    )
    wav = tmp_path / "u.wav"
    wav.write_bytes(b"RIFF")
    stt.transcribe(wav, duration_s=1.0)
    args = eval((fake_whisper_cli.parent / (fake_whisper_cli.name + ".log")).read_text())
    assert "--vad" in args
    assert args[args.index("-vm") + 1] == str(vad_model)


def test_transcribe_selects_small_for_long_utterance(
    fake_whisper_cli: Path, tmp_path: Path
) -> None:
    stt = WhisperSTT(
        whisper_cli=fake_whisper_cli,
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
    )
    wav = tmp_path / "u.wav"
    wav.write_bytes(b"RIFF")
    stt.transcribe(wav, duration_s=8.0)
    args = eval((fake_whisper_cli.parent / (fake_whisper_cli.name + ".log")).read_text())
    assert args[1].endswith("small.bin")


def test_transcribe_raises_on_nonzero_exit(tmp_path: Path) -> None:
    failing = tmp_path / "whisper-cli"
    failing.write_text("#!/bin/sh\necho 'boom' >&2\nexit 2\n")
    failing.chmod(0o755)
    stt = WhisperSTT(
        whisper_cli=failing,
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
    )
    wav = tmp_path / "u.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(STTError) as exc:
        stt.transcribe(wav, duration_s=1.0)
    assert "whisper-cli" in str(exc.value)


def test_stt_error_is_exception_type() -> None:
    assert issubclass(STTError, Exception)


def test_missing_wav_raises_stterror(tmp_path: Path) -> None:
    stt = WhisperSTT(
        whisper_cli=tmp_path / "whisper-cli",
        model_small=tmp_path / "small.bin",
        model_medium=tmp_path / "medium.bin",
        prompt=FIXTURE_PROMPT,
    )
    with pytest.raises(STTError):
        stt.transcribe(tmp_path / "missing.wav", duration_s=1.0)
