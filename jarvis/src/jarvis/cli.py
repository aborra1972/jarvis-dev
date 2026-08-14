"""Command-line interface.

Exposes the lifecycle/switch commands from the assistant-lifecycle spec
(`jarvis start/stop/off/on/clean/logs`). start/off/on are wired to the
orchestrator (PR3); stop/clean/logs stay loud stubs until PR6.
"""

from __future__ import annotations

import argparse
import sys

from jarvis.orchestrator import loop

COMMANDS = ("start", "stop", "off", "on", "clean", "logs")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``jarvis`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="Jarvis de Desarrollo — local voice assistant",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for cmd in COMMANDS:
        sub.add_parser(cmd, help=f"{cmd}")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "start":
        return loop.start()
    if args.command == "off":
        return loop.switch_off()
    if args.command == "on":
        return loop.switch_on()
    print(f"{args.command}: not implemented yet (bootstrap skeleton)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
