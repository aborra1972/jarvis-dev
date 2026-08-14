"""Task 6.3 WU1: `jarvis clean` + local deletable logs (RNF-3, RF-11).

Covers the assistant-lifecycle spec "Deletable local logs" scenarios:
- capture wavs, reply wavs and transcripts are written under LOGS_DIR;
- `jarvis clean` deletes them and confirms;
- state.json (RF-6 session + the RF-11 off switch) and config are preserved.
"""

from __future__ import annotations

from pathlib import Path

from jarvis import config
from jarvis.orchestrator import loop
from jarvis.orchestrator.logs import TranscriptLog, clean_logs
from jarvis.orchestrator.session import Session


def test_clean_logs_deletes_every_file_and_counts(tmp_path: Path) -> None:
    capture = tmp_path / "capture"
    reply = tmp_path / "reply"
    capture.mkdir(parents=True)
    reply.mkdir()
    (capture / "a.wav").write_bytes(b"RIFF")
    (reply / "b.wav").write_bytes(b"RIFF")
    (tmp_path / "transcripts.jsonl").write_text("{}\n")

    deleted = clean_logs(tmp_path)

    assert deleted == 3
    assert not list(tmp_path.rglob("*.wav"))
    assert not (tmp_path / "transcripts.jsonl").exists()


def test_clean_logs_no_op_on_empty_logs_dir(tmp_path: Path) -> None:
    assert clean_logs(tmp_path) == 0


def test_clean_logs_preserves_sibling_state_json(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    state = tmp_path / "state.json"
    logs.mkdir()
    (logs / "x.wav").write_bytes(b"RIFF")
    state.write_text('{"switched_off": true}')

    deleted = clean_logs(logs)

    assert deleted == 1
    assert state.read_text() == '{"switched_off": true}'


def test_transcript_log_appends_jsonl_records(tmp_path: Path) -> None:
    path = tmp_path / "transcripts.jsonl"
    log = TranscriptLog(path)

    log.record("abrí firefox", intent="open_app", outcome="execute")
    log.record("cerrá linux", intent="shutdown", outcome="confirm")

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert '"abrí firefox"' in lines[0]
    assert '"open_app"' in lines[0]
    assert '"cerrá linux"' in lines[1]
    assert '"shutdown"' in lines[1]


def test_transcript_log_skips_empty_transcripts(tmp_path: Path) -> None:
    path = tmp_path / "transcripts.jsonl"
    log = TranscriptLog(path)

    log.record("", intent=None, outcome="silence")

    assert not path.exists()


def test_clean_command_deletes_logs_and_preserves_state(tmp_path: Path, monkeypatch) -> None:
    logs = tmp_path / "logs"
    capture = logs / "capture"
    capture.mkdir(parents=True)
    (capture / "a.wav").write_bytes(b"RIFF")
    state = tmp_path / "state.json"
    state.write_text('{"active_project": "/repo", "switched_off": false}')
    monkeypatch.setattr(config, "LOGS_DIR", logs)

    code = loop.clean()

    assert code == 0
    assert not list(logs.rglob("*.wav"))
    assert state.read_text() == '{"active_project": "/repo", "switched_off": false}'


def test_clean_command_confirms_even_with_no_logs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(config, "LOGS_DIR", tmp_path / "missing")

    code = loop.clean()

    assert code == 0
    assert "no había logs" in capsys.readouterr().err


def test_build_pipeline_writes_logs_under_logs_dir(monkeypatch) -> None:
    calls: dict[str, dict] = {}

    def _rec(name: str):
        class Recorder:
            def __init__(self, *args, **kwargs) -> None:
                calls[name] = kwargs

        Recorder.__name__ = name
        return Recorder

    for name in ("SoundDeviceCapturer", "OpenWakeWord", "WhisperSTT", "PiperTTS", "Playback"):
        monkeypatch.setattr(loop, name, _rec(name), raising=False)
    monkeypatch.setattr(loop, "UtteranceCapture", _rec("UtteranceCapture"))
    monkeypatch.setattr(loop, "PiperSpeaker", _rec("PiperSpeaker"))
    monkeypatch.setattr(loop, "MicSwitch", lambda *a, **k: (lambda: False))
    monkeypatch.setattr(loop, "build_registry", lambda: "executor")

    pipeline = loop.build_pipeline(Session(), cwd="/tmp")

    assert calls["UtteranceCapture"]["wav_dir"] == config.LOGS_CAPTURE_DIR
    assert calls["PiperSpeaker"]["out_dir"] == config.LOGS_REPLY_DIR
    assert pipeline.transcript_log.path == config.TRANSCRIPTS_FILE
