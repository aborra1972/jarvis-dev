"""Text-to-speech tests (PR5, task 5.4).

Design ADR-5: piper subprocess wrapper (es_AR-daniela) with the config file,
20s timeout, text piped via stdin and output to `-f wav`. Tests run against a
fake piper script that materializes the wav file and logs its args.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.audio.tts import TTSError, PiperTTS


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
    model = tmp_path / "es_AR-daniela-high.onnx"
    config = tmp_path / "es_AR-daniela-high.onnx.json"
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
