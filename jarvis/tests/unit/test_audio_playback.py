"""Playback tests (PR5, task 5.5).

The Speaker pipeline hands TTS audio to a player binary via a list-args
subprocess call — wav to paplay (piper) and mp3 to gst-launch-1.0 playbin
(edge-tts), picked by file suffix. Tests run against fake player scripts that
log their args and exit 0.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.audio.playback import Playback, PlaybackError


def test_play_invokes_player_with_wav(tmp_path: Path) -> None:
    player = tmp_path / "paplay"
    player.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "open(sys.argv[0] + '.log', 'w').write(json.dumps(sys.argv[1:]))\n"
    )
    player.chmod(0o755)
    wav = tmp_path / "reply.wav"
    wav.write_bytes(b"RIFF")

    Playback(player=player).play(wav)

    args = eval((player.parent / (player.name + ".log")).read_text())
    assert args == [str(wav)]


def test_play_invokes_gst_playbin_with_mp3(tmp_path: Path) -> None:
    player = tmp_path / "paplay"
    player.write_text("#!/bin/sh\nexit 0\n")
    player.chmod(0o755)
    gst = tmp_path / "gst-launch-1.0"
    gst.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "open(sys.argv[0] + '.log', 'w').write(json.dumps(sys.argv[1:]))\n"
    )
    gst.chmod(0o755)
    mp3 = tmp_path / "reply.mp3"
    mp3.write_bytes(b"MP3fake")

    Playback(player=player, mp3_player=gst).play(mp3)

    args = eval((gst.parent / (gst.name + ".log")).read_text())
    assert args[0] == "playbin"
    assert args[1] == f"uri=file://{mp3.resolve()}"


def test_play_raises_on_nonzero_exit(tmp_path: Path) -> None:
    failing = tmp_path / "paplay-fail"
    failing.write_text("#!/bin/sh\necho 'device busy' >&2\nexit 1\n")
    failing.chmod(0o755)
    wav = tmp_path / "reply.wav"
    wav.write_bytes(b"RIFF")
    with pytest.raises(PlaybackError) as exc:
        Playback(player=failing).play(wav)
    assert "paplay" in str(exc.value)


def test_playback_error_is_exception_type() -> None:
    assert issubclass(PlaybackError, Exception)
