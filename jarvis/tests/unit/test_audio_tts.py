"""Text-to-speech tests (PR5, task 5.4).

Design ADR-5: piper subprocess wrapper (es_MX-ald-medium) with the config file,
20s timeout, text piped via stdin and output to `-f wav`. Tests run against a
fake piper script that materializes the wav file and logs its args.

Edge TTS upgrade: the primary engine is EdgeTTS (es-MX-JorgeNeural) via the
edge-tts CLI — text on the command line, output to `--write-media` mp3, 60s
timeout. Tests run against a fake edge-tts script that materializes the mp3
and logs its args. PiperTTS stays as the offline fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.audio.tts import TTSError, EdgeTTS, PiperTTS


@pytest.fixture
def fake_piper(tmp_path: Path) -> Path:
    script = tmp_path / "piper"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "log = open(sys.argv[0] + '.log', 'w')\n"
        "json.dump(args, log)\n"
        "log.close()\n"
        "out = args[args.index('-f') + 1] if '-f' in args else 'out.wav'\n"
        "open(out, 'wb').write(b'RIFFfakewav')\n"
    )
    script.chmod(0o755)
    return script


def test_synthesize_builds_piper_command(
    fake_piper: Path, tmp_path: Path
) -> None:
    model = tmp_path / "es_MX-ald-medium.onnx"
    config = tmp_path / "es_MX-ald-medium.onnx.json"
    model.write_bytes(b"onnx")
    config.write_bytes(b"{}")
    tts = PiperTTS(piper_bin=fake_piper, model=model, config=config)

    out = tmp_path / "reply.wav"
    result = tts.synthesize("cerrá la terminal", out)

    assert result == out
    assert out.read_bytes() == b"RIFFfakewav"
    args = eval((fake_piper.parent / (fake_piper.name + ".log")).read_text())
    assert args[0] == "-m"
    assert args[1] == str(model)
    assert args[2] == "-c"
    assert args[3] == str(config)
    assert args[4] == "-f"
    assert args[5] == str(out)


def test_synthesize_writes_text_to_stdin(fake_piper: Path, tmp_path: Path) -> None:
    model = tmp_path / "model.onnx"
    config = tmp_path / "model.onnx.json"
    model.write_bytes(b"onnx")
    config.write_bytes(b"{}")
    text = "abrí el navegador"
    log = tmp_path / "stdin.txt"
    script = tmp_path / "piper2"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "from pathlib import Path\n"
        "open(sys.argv[0] + '.stdin', 'w').write(sys.stdin.read())\n"
        "(Path(sys.argv[0]).parent / 'x.wav').write_bytes(b'wav')\n"
    )
    script.chmod(0o755)
    tts = PiperTTS(piper_bin=script, model=model, config=config)
    tts.synthesize(text, tmp_path / "out.wav")
    assert (script.parent / (script.name + ".stdin")).read_text() == text


def test_synthesize_raises_on_nonzero_exit(tmp_path: Path) -> None:
    failing = tmp_path / "piper-fail"
    failing.write_text("#!/bin/sh\necho 'no model' >&2\nexit 1\n")
    failing.chmod(0o755)
    tts = PiperTTS(
        piper_bin=failing,
        model=tmp_path / "model.onnx",
        config=tmp_path / "model.onnx.json",
    )
    with pytest.raises(TTSError) as exc:
        tts.synthesize("hola", tmp_path / "out.wav")
    assert "piper" in str(exc.value)


def test_tts_error_is_exception_type() -> None:
    assert issubclass(TTSError, Exception)


@pytest.fixture
def fake_edge_tts(tmp_path: Path) -> Path:
    script = tmp_path / "edge-tts"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "args = sys.argv[1:]\n"
        "open(sys.argv[0] + '.log', 'w').write(json.dumps(args))\n"
        "out = args[args.index('--write-media') + 1] if '--write-media' in args else 'out.mp3'\n"
        "open(out, 'wb').write(b'MP3fake')\n"
    )
    script.chmod(0o755)
    return script


def _edge_args(fake_edge_tts: Path) -> list[str]:
    return eval((fake_edge_tts.parent / (fake_edge_tts.name + ".log")).read_text())


def test_edge_synthesize_builds_command(fake_edge_tts: Path, tmp_path: Path) -> None:
    tts = EdgeTTS(bin_path=fake_edge_tts, voice="es-MX-JorgeNeural")

    out = tmp_path / "reply.mp3"
    result = tts.synthesize("cerrá la terminal", out)

    assert result == out
    assert out.read_bytes() == b"MP3fake"
    args = _edge_args(fake_edge_tts)
    assert args[0] == "--voice"
    assert args[1] == "es-MX-JorgeNeural"
    assert args[2] == "--text"
    assert args[3] == "cerrá la terminal"
    assert args[4] == "--write-media"
    assert args[5] == str(out)


def test_edge_synthesize_passes_rate_and_pitch(fake_edge_tts: Path, tmp_path: Path) -> None:
    tts = EdgeTTS(
        bin_path=fake_edge_tts,
        voice="es-MX-JorgeNeural",
        rate="-10%",
        pitch="-5Hz",
    )

    tts.synthesize("hola", tmp_path / "reply.mp3")

    args = _edge_args(fake_edge_tts)
    assert args[6] == "--rate"
    assert args[7] == "-10%"
    assert args[8] == "--pitch"
    assert args[9] == "-5Hz"


def test_edge_synthesize_omits_rate_and_pitch_by_default(
    fake_edge_tts: Path, tmp_path: Path
) -> None:
    tts = EdgeTTS(bin_path=fake_edge_tts, voice="es-MX-JorgeNeural")

    tts.synthesize("hola", tmp_path / "reply.mp3")

    assert _edge_args(fake_edge_tts) == [
        "--voice",
        "es-MX-JorgeNeural",
        "--text",
        "hola",
        "--write-media",
        str(tmp_path / "reply.mp3"),
    ]


def test_edge_synthesize_raises_on_nonzero_exit(tmp_path: Path) -> None:
    failing = tmp_path / "edge-tts-fail"
    failing.write_text("#!/bin/sh\necho 'network error' >&2\nexit 1\n")
    failing.chmod(0o755)
    tts = EdgeTTS(bin_path=failing, voice="es-MX-JorgeNeural")
    with pytest.raises(TTSError) as exc:
        tts.synthesize("hola", tmp_path / "reply.mp3")
    assert "edge-tts" in str(exc.value)


def test_edge_synthesize_raises_on_timeout(tmp_path: Path) -> None:
    slow = tmp_path / "edge-tts-slow"
    slow.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(5)\n")
    slow.chmod(0o755)
    tts = EdgeTTS(bin_path=slow, voice="es-MX-JorgeNeural", timeout_s=0.05)
    with pytest.raises(TTSError):
        tts.synthesize("hola", tmp_path / "reply.mp3")


def test_edge_synthesize_raises_when_output_not_written(tmp_path: Path) -> None:
    noop = tmp_path / "edge-tts-noop"
    noop.write_text("#!/bin/sh\nexit 0\n")
    noop.chmod(0o755)
    tts = EdgeTTS(bin_path=noop, voice="es-MX-JorgeNeural")
    with pytest.raises(TTSError) as exc:
        tts.synthesize("hola", tmp_path / "reply.mp3")
    assert "output" in str(exc.value)


def test_engines_expose_extension_for_the_speaker() -> None:
    assert EdgeTTS.extension == ".mp3"
    assert PiperTTS.extension == ".wav"
