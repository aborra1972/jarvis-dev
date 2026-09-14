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
    resolve_spotify_client_id, SPOTIFY_LIVE_TIMEOUT_DEFAULT_S,
    SPOTIFY_LIVE_TIMEOUT_MAX_S, KeyringCredentialStore,
    create_spotify_oauth_client, SpotifyCatalogBridge, CatalogBridgeCode,
    PlaybackPolicy, PlaybackCode, SpotifyPlaybackBridge,
    discover_spotify_identities, spotify_device_fingerprint,
    spotify_device_type_category,
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


def _handle_spotify_target_setup(*, writer=None) -> int:
    """Enroll one confirmed Spotify Desktop API device without exposing its ID."""
    from jarvis import config
    configuration, store, transport = _spotify_search_dependencies()
    if configuration.get("enabled") is not True or configuration.get("authorized") is not True:
        print("jarvis spotify target setup: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    identities = _spotify_playback_dependencies()[1]()
    if identities != ["spotify"]:
        print("jarvis spotify target setup: Spotify MPRIS is not uniquely available.", file=sys.stderr)
        return 1
    client = create_spotify_oauth_client(configuration, store=store, transport=transport)
    if client is None:
        print("jarvis spotify target setup: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    try:
        payload = SpotifyPlaybackBridge(oauth=client)("GET", PlaybackPolicy.DEVICES_URL, None, 5.0)
    except Exception:
        print("jarvis spotify target setup: provider failure; target unchanged.", file=sys.stderr)
        return 1
    devices = payload.get("devices") if isinstance(payload, dict) else None
    if not isinstance(devices, list):
        print("jarvis spotify target setup: malformed provider response; target unchanged.", file=sys.stderr)
        return 1
    valid = []
    for device in devices:
        if (not isinstance(device, dict)
                or spotify_device_type_category(device.get("type")) != "computer"):
            continue
        try:
            fingerprint = spotify_device_fingerprint(device.get("id"))
        except ValueError:
            continue
        name = device.get("name") if isinstance(device.get("name"), str) else "unnamed device"
        name = "".join(ch if ch.isprintable() and ch not in "\\x00\\x1f\\x7f" else "?" for ch in name).strip()[:40] or "unnamed device"
        valid.append((fingerprint, name))
    if not valid:
        print("jarvis spotify target setup: no valid computer target; target unchanged.", file=sys.stderr)
        return 1
    try:
        if len(valid) == 1:
            print(f"Spotify Desktop target: {valid[0][1]} (computer)")
            selected = valid[0] if input("Enroll this target? (yes/no): ").strip().casefold() == "yes" else None
        else:
            print("Spotify Desktop targets:")
            for number, (_, name) in enumerate(valid, 1):
                print(f"  {number}. {name} (computer)")
            answer = input("Choose an exact target ordinal (Enter cancels): ").strip()
            selected = valid[int(answer) - 1] if answer.isdigit() and 1 <= int(answer) <= len(valid) else None
            if selected is not None and input("Enroll this target? (yes/no): ").strip().casefold() != "yes":
                selected = None
    except (EOFError, KeyboardInterrupt, ValueError):
        selected = None
    if selected is None:
        print("Spotify target enrollment cancelled; target unchanged.", file=sys.stderr)
        return 1
    try:
        (writer or config.set_spotify_target_fingerprint)(selected[0])
    except Exception:
        print("jarvis spotify target setup: configuration write failed; target unchanged.", file=sys.stderr)
        return 1
    print("Spotify target enrolled.")
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


def _handle_spotify_live_authorize(timeout_s: float = SPOTIFY_LIVE_TIMEOUT_DEFAULT_S) -> int:
    """Run the explicit live OAuth flow; all capabilities remain bounded/injected."""
    import webbrowser
    from jarvis import config
    from jarvis.services.spotify import (
        KeyringCredentialStore, OAuthCallbackCode, OAuthErrorCode,
    )

    result = run_spotify_live_authorization(
        config.load_spotify_oauth_config(), browser_opener=webbrowser.open,
        server_factory=_create_loopback_server, transport=_urllib_transport,
        store=KeyringCredentialStore(), timeout_s=timeout_s,
    )
    if result.code is OAuthErrorCode.OK:
        print("Spotify autorizado correctamente.")
        return 0
    if isinstance(result.callback_code, OAuthCallbackCode):
        message = result.callback_diagnostic or result.callback_code.value
    else:
        message = (result.diagnostic
                   if result.diagnostic in {"token_http_400", "token_http_401", "token_http_other"}
                   else result.message)
    print(f"{result.code.value}: {message}", file=sys.stderr)
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


def _spotify_search_dependencies():
    from jarvis import config
    return config.load_spotify_oauth_config(), KeyringCredentialStore(), _urllib_transport


def _spotify_playback_dependencies():
    from jarvis import config
    return config.load_spotify_playback_config(), lambda: discover_spotify_identities(
        config.SPOTIFY_PLAYERCTL_BIN, config.SPOTIFY_MPRIS_IDENTITY,
    )


def _handle_spotify_search_and_play(args: argparse.Namespace) -> int:
    configuration, store, transport = _spotify_search_dependencies()
    if configuration.get("enabled") is not True or configuration.get("authorized") is not True:
        print("jarvis spotify search-and-play: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    playback_config, local_identity = _spotify_playback_dependencies()
    fingerprint = playback_config.get("target_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        print("jarvis spotify search-and-play: target is not configured.", file=sys.stderr)
        return 1
    client = create_spotify_oauth_client(configuration, store=store, transport=transport)
    if client is None:
        print("jarvis spotify search-and-play: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    bridge = SpotifyCatalogBridge(oauth=client, transport=transport)
    result = bridge.search(args.kind, args.query, session_id="cli", limit=args.limit)
    if result.code is not CatalogBridgeCode.OK or result.catalog is None or not result.catalog.candidates:
        print(f"jarvis spotify search-and-play: {result.code.value}.", file=sys.stderr)
        return 1
    for number, candidate in enumerate(result.catalog.candidates, 1):
        print(f"{number}. {candidate.name} — {candidate.artist or 'unknown artist'} ({candidate.kind})")
    try:
        choice = input("Elegí un resultado por número (Enter cancela): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("Selección cancelada.", file=sys.stderr)
        return 1
    if not choice.isdigit() or not 1 <= int(choice) <= len(result.catalog.candidates):
        print("Selección cancelada.", file=sys.stderr)
        return 1
    selected = result.catalog.candidates[int(choice) - 1]
    policy = PlaybackPolicy(
        api=SpotifyPlaybackBridge(oauth=client), local_identity=local_identity,
        configured_fingerprint=fingerprint, scopes=configuration.get("scopes"),
    )
    outcome = policy.play_selection(bridge.catalog, selected.selection_id, session_id="cli")
    if outcome.code is not PlaybackCode.OK:
        print(f"jarvis spotify search-and-play: {outcome.code.value}.", file=sys.stderr)
        return 1
    print(f"Reproduciendo {selected.name} — {selected.artist or 'unknown artist'} ({selected.kind}).")
    return 0


def _handle_spotify_search(args: argparse.Namespace) -> int:
    configuration, store, transport = _spotify_search_dependencies()
    if configuration.get("enabled") is not True or configuration.get("authorized") is not True:
        print("jarvis spotify search: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    client = create_spotify_oauth_client(configuration, store=store, transport=transport)
    if client is None:
        print("jarvis spotify search: Spotify API disabled or unauthorized.", file=sys.stderr)
        return 1
    bridge = SpotifyCatalogBridge(oauth=client, transport=transport)
    result = bridge.search(args.kind, args.query, session_id="cli", limit=args.limit)
    if result.code is not CatalogBridgeCode.OK or result.catalog is None:
        print(f"jarvis spotify search: {result.code.value}.", file=sys.stderr)
        return 1
    for candidate in result.catalog.candidates:
        print(f"{candidate.name}\t{candidate.kind}\t{candidate.selection_id}")
    return 0


def _parse_spotify_search(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jarvis spotify search")
    parser.add_argument("--kind", choices=("album", "artist"), required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 10:
        parser.error("--limit must be between 1 and 10")
    return args


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    parser = build_parser()
    # Keep the historical top-level command list stable while accepting the
    # clearer Spotify setup spelling as an equivalent alias.
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    if effective_argv[:2] in (["spotify", "search"], ["spotify", "search-and-play"]):
        parsed = _parse_spotify_search(effective_argv[2:])
        if effective_argv[1] == "search-and-play":
            return _handle_spotify_search_and_play(parsed)
        return _handle_spotify_search(parsed)
    if effective_argv[:3] == ["spotify", "authorize", "--live"]:
        timeout_s = SPOTIFY_LIVE_TIMEOUT_DEFAULT_S
        remaining = effective_argv[3:]
        if remaining:
            if len(remaining) != 2 or remaining[0] != "--timeout":
                print("jarvis spotify authorize: uso: --live [--timeout SECONDS]", file=sys.stderr)
                return 2
            try:
                timeout_s = float(remaining[1])
            except ValueError:
                print("jarvis spotify authorize: timeout inválido", file=sys.stderr)
                return 2
            if not 0.1 <= timeout_s <= SPOTIFY_LIVE_TIMEOUT_MAX_S:
                print(f"jarvis spotify authorize: timeout debe estar entre 0.1 y {SPOTIFY_LIVE_TIMEOUT_MAX_S:g} segundos", file=sys.stderr)
                return 2
        return _handle_spotify_live_authorize(timeout_s)
    if effective_argv == ["spotify", "authorize"]:
        return _handle_spotify_authorize()
    if effective_argv == ["spotify", "target", "setup"]:
        return _handle_spotify_target_setup()
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
