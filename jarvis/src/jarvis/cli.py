"""Command-line interface.

Exposes the lifecycle/switch commands from the assistant-lifecycle spec
(``jarvis start/stop/off/on/clean/logs``), the ``jarvis say`` TTS CLI
for scripts and OpenCode integration, and the agent/persona selector
(``jarvis agent`` / ``jarvis setup``) that persists JARVIS_AGENT in the
repo-root .env.
"""

from __future__ import annotations

import argparse
import getpass
import subprocess
import sys
import tempfile
import secrets
import time
from pathlib import Path

from jarvis.orchestrator import loop
from jarvis.services.spotify import (
    ClientIdStatus, KeyringClientIdStore, create_pkce_transaction,
    create_spotify_authorization, redacted_authorization_url,
        run_spotify_live_authorization, _create_loopback_server, _urllib_transport,
    resolve_spotify_client_id,
)

COMMANDS = (
    "start", "stop", "off", "on", "clean", "logs", "say", "ptt", "diagnose",
    "agent", "setup",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level ``jarvis`` argument parser."""
    from jarvis import config

    parser = argparse.ArgumentParser(
        prog="jarvis",
        description=f"{config.agent_name()} — local voice assistant",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for cmd in COMMANDS:
        if cmd == "say":
            p = sub.add_parser(cmd, help="speak text via TTS (for scripts/OpenCode)")
            p.add_argument("text", nargs="*", help="text to speak (or '-' for stdin)")
            p.add_argument("--detach", "-d", action="store_true",
                           help="don't wait for playback to finish")
            p.add_argument("--voice", default=None,
                           help="override TTS voice (default: voz del agente activo — config.EDGE_VOICE)")
        elif cmd == "agent":
            p = sub.add_parser(cmd, help="ver o cambiar el agente/personaje (jarvis|friday|karen)")
            p.add_argument("name", nargs="?", default=None,
                           help="agente a activar (jarvis|friday|karen); sin argumento muestra el actual")
        elif cmd == "setup":
            p = sub.add_parser(cmd, help="wizard de configuración: elegir agente/personaje")
            p.add_argument("name", nargs="?", default=None,
                           help="agente a configurar (no interactivo); sin argumento pregunta")
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


def _handle_agent(args: argparse.Namespace) -> int:
    """``jarvis agent [name]``: show the active agent or switch persona.

    With no name, prints the active agent, its edge-tts voice and personality.
    With a valid name writes JARVIS_AGENT=<name> into the repo-root .env (the
    switch applies on the next run — the running process keeps its persona).
    Unknown names are rejected with a non-zero exit.
    """
    from jarvis import config

    if args.name is None:
        profile = config.AGENT_PROFILES[config.AGENT]
        print(f"Agente activo: {config.AGENT} ({profile['name']})")
        print(f"Voz: {config.EDGE_VOICE}")
        print(f"Tratamiento: {profile['address']}")
        print(f"Personalidad: {profile['personality']}")
        return 0

    name = args.name.strip().lower()
    if name not in config.AGENT_PROFILES:
        print(
            f"jarvis agent: agente desconocido '{args.name}'. "
            f"Válidos: {', '.join(sorted(config.AGENT_PROFILES))}",
            file=sys.stderr,
        )
        return 1
    config.set_agent(name)
    profile = config.AGENT_PROFILES[name]
    print(f"Agente cambiado a {profile['name']} (voz: {profile['voice']}).")
    print("El cambio se aplica al reiniciar jarvis.")
    return 0


def _handle_spotify_setup() -> int:
    """Read and save a Spotify Client ID without exposing or persisting it."""
    if not sys.stdin.isatty():
        print("jarvis spotify setup: requiere modo interactivo.", file=sys.stderr)
        return 1
    try:
        client_id = getpass.getpass("Spotify Client ID (no se muestra): ")
    except (EOFError, KeyboardInterrupt, OSError) as exc:
        print(f"jarvis spotify setup: no se pudo leer el Client ID ({exc}).", file=sys.stderr)
        return 1
    store = KeyringClientIdStore()
    validated = resolve_spotify_client_id(client_id.strip(), store=store)
    if validated.status is ClientIdStatus.INVALID:
        print("jarvis spotify setup: Client ID inválido.", file=sys.stderr)
        return 1
    result = store.save(client_id.strip())
    if result.status is ClientIdStatus.INVALID:
        print("jarvis spotify setup: Client ID inválido.", file=sys.stderr)
        return 1
    if result.status is not ClientIdStatus.OK:
        print("jarvis spotify setup: el keyring del sistema no está disponible.", file=sys.stderr)
        return 1
    print("Spotify configurado: Client ID guardado únicamente en el keyring del sistema.")
    return 0


def _handle_spotify_live_authorize() -> int:
    """Run the explicit live OAuth flow; all capabilities remain bounded/injected."""
    import webbrowser
    from jarvis import config
    from jarvis.services.spotify import KeyringCredentialStore, OAuthErrorCode

    result = run_spotify_live_authorization(
        config.load_spotify_oauth_config(), browser_opener=webbrowser.open,
        server_factory=_create_loopback_server, transport=_urllib_transport,
        store=KeyringCredentialStore(),
    )
    if result.code is OAuthErrorCode.OK:
        print("Spotify autorizado correctamente.")
        return 0
    print(result.message, file=sys.stderr)
    return 1


def _handle_spotify_authorize() -> int:
    """Construct, but do not execute, the explicitly gated authorization URL."""
    from jarvis import config

    configuration = config.load_spotify_oauth_config()
    session_id = secrets.token_urlsafe(16)
    try:
        transaction = create_pkce_transaction(
            session_id, now=time.time(),
            ttl_s=float(configuration.get("transaction_ttl_s", 300.0)),
        )
    except (TypeError, ValueError):
        transaction = None
    url = (create_spotify_authorization(
        configuration, transaction=transaction,
        allow_pending_authorization=True,
    ) if transaction is not None else None)
    if not url:
        print("jarvis spotify authorize: autorización no disponible; revise el gate de Spotify.",
              file=sys.stderr)
        return 1
    print("Spotify authorization URL constructed (not opened):")
    print(redacted_authorization_url(url))
    return 0


def _handle_setup(args: argparse.Namespace) -> int:
    """``jarvis setup [name]``: wizard to pick the agent/persona or Spotify.

    Lists the 3 agents; with no name it prompts interactively (number or
    name). Persists JARVIS_AGENT=<name> in the repo-root .env.
    """
    if args.name is not None and args.name.strip().lower() == "spotify":
        return _handle_spotify_setup()

    from jarvis import config

    profiles = config.AGENT_PROFILES
    keys = list(profiles)  # canonical order: jarvis, friday, karen
    print("Agentes disponibles:")
    for idx, key in enumerate(keys, 1):
        p = profiles[key]
        print(f"  {idx}. {key} — {p['name']} (voz: {p['voice']})")

    if args.name:
        choice = args.name.strip().lower()
    else:
        try:
            choice = input("Elegí un agente (número o nombre, Enter cancela): ").strip().lower()
        except EOFError:
            choice = ""
    if not choice:
        print("Setup cancelado. Agente actual sin cambios.")
        return 0
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(keys):
            choice = keys[idx - 1]
        else:
            print(f"jarvis setup: número inválido '{choice}'.", file=sys.stderr)
            return 1
    if choice not in profiles:
        print(
            f"jarvis setup: agente desconocido '{choice}'. "
            f"Válidos: {', '.join(sorted(profiles))}",
            file=sys.stderr,
        )
        return 1
    config.set_agent(choice)
    print(f"Agente configurado: {profiles[choice]['name']} (voz: {profiles[choice]['voice']}).")
    print("El cambio se aplica al reiniciar jarvis.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    # Keep the historical top-level command list stable while accepting the
    # clearer Spotify setup spelling as an equivalent alias.
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv == ["spotify", "authorize", "--live"]:
        return _handle_spotify_live_authorize()
    if effective_argv == ["spotify", "authorize"]:
        return _handle_spotify_authorize()
    if effective_argv == ["spotify", "setup"]:
        effective_argv = ["setup", "spotify"]
    args = parser.parse_args(effective_argv)
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
    if args.command == "ptt":
        return loop.request_voice_turn("cli_ptt")
    if args.command == "clean":
        return loop.clean()
    if args.command == "agent":
        return _handle_agent(args)
    if args.command == "setup":
        return _handle_setup(args)
    if args.command == "diagnose":
        from jarvis import diagnose
        return diagnose.main()
    print(f"{args.command}: not implemented yet (bootstrap skeleton)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
