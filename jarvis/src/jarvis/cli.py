"""Command-line interface (bootstrap skeleton).

Exposes the lifecycle/switch commands from the assistant-lifecycle spec
(`jarvis start/stop/off/on/clean/logs`). Commands are stubs that fail loudly
until their PRs land: start/stop wiring in PR6 (loop.py), off/on switch in
PR5 (voice) + PR6, clean in PR6 (RNF-3), logs in PR6.
"""

from __future__ import annotations

import argparse
import sys

COMMANDS = ("start", "stop", "off", "on", "clean", "logs")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``jarvis`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis de Desarrollo — local voice assistant",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for cmd in COMMANDS:
        sub.add_parser(cmd, help=f"{cmd} (bootstrap stub)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    print(f"{args.command}: not implemented yet (bootstrap skeleton)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
