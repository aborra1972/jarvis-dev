"""Command-line interface.

Exposes the lifecycle/switch commands from the assistant-lifecycle spec
(``jarvis start/stop/off/on/clean/logs``) and the ``jarvis say`` TTS CLI
for scripts and OpenCode integration.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from jarvis.orchestrator import loop

COMMANDS = ("start", "stop", "off", "on", "clean", "logs", "say", "diagnose")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``jarvis`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis de Desarrollo — local voice assistant",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for cmd in COMMANDS:
        if cmd == "say":
            p = sub.add_parser(cmd, help="speak text via TTS (for scripts/OpenCode)")
            p.add_argument("text", nargs="*", help="text to speak (or '-' for stdin)")
            p.add_argument("--detach", "-d", action="store_true",
                           help="don't wait for playback to finish")
            p.add_argument("--voice", default=None,
                           help="override TTS voice (default: es-MX-JorgeNeural)")
        else:
            sub.add_parser(cmd, help=f"{cmd}")
    return parser


def _handle_say(args: argparse.Namespace) -> int:
    """``jarvis say``: synthesize text with Edge TTS and play it.

    Supports:
    - ``jarvis say "hello world"`` — speak inline text
    - ``echo "text" | jarvis say -`` — speak from stdin
    - ``jarvis say -d "background"`` — detach (don't block terminal)
    """
    from jarvis import config

    # Resolve text: stdin if "-" or no args
    text = " ".join(args.text) if args.text and args.text != ["-"] else None
    if text is None:
        if sys.stdin.isatty():
            print("jarvis say: no text provided (use 'jarvis say \"text\"' or pipe to stdin)",
                  file=sys.stderr)
            return 1
        text = sys.stdin.read().strip()
    if not text:
        return 0

    voice = args.voice or config.EDGE_VOICE
    bin_path = config.EDGE_TTS_BIN

    # Synthesize to temp file
    suffix = ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        out_path = Path(tmp.name)

    cmd = [
        str(bin_path),
        "--voice", voice,
        "--text", text,
        "--write-media", str(out_path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"jarvis say: edge-tts failed: {exc}", file=sys.stderr)
        out_path.unlink(missing_ok=True)
        return 1

    if proc.returncode != 0:
        print(f"jarvis say: edge-tts exited {proc.returncode}: {proc.stderr.strip()}",
              file=sys.stderr)
        out_path.unlink(missing_ok=True)
        return 1

    # Play
    play_cmd = ["gst-launch-1.0", "playbin", f"uri=file://{out_path.resolve()}"]
    if args.detach:
        subprocess.Popen(play_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 0

    try:
        subprocess.run(play_cmd, capture_output=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, OSError):
        pass
    finally:
        out_path.unlink(missing_ok=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "say":
        return _handle_say(args)
    if args.command == "start":
        return loop.start()
    if args.command == "off":
        return loop.switch_off()
    if args.command == "on":
        return loop.switch_on()
    if args.command == "clean":
        return loop.clean()
    if args.command == "diagnose":
        from jarvis import diagnose
        return diagnose.main()
    print(f"{args.command}: not implemented yet (bootstrap skeleton)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
