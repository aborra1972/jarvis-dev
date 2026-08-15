"""Playback tests (PR5, task 5.5).

The Speaker pipeline hands piper's wav to a player binary (paplay by default)
via a list-args subprocess call. Tests run against a fake player that logs its
args and exits 0.
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
