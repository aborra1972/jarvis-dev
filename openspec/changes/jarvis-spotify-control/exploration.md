# Exploration: Spotify control (`jarvis-spotify-control`)

## Status and boundary

Stage 0 capability spike completed. This artifact records a documentation-only, read-only reconciliation: no source code, tests, configuration, dependency manifests, OAuth material, credentials, or existing specifications were changed. Later implementation MUST follow the repository's strict TDD sequence (RED → GREEN → TRIANGULATE → REFACTOR); tests were not required or run for this provider-authorized spike.

- Repository: `/home/ale/Proyectos/jarvis-dev` (symlinked real path is recorded in `openspec/config.yaml`).
- `skill_resolution: fallback-path` — no parent-injected project/phase skill path was supplied; the generic Gentle AI skill was loaded from its indexed path.
- Authoritative artifact store: OpenSpec files under `openspec/changes/jarvis-spotify-control/`.
- Read-only context: `openspec/config.yaml`, current `system-control`, `command-interpreter`, `web-actions`, and `voice-pipeline` specifications; interpreter schema/golden gate; system executor/registry; runtime configuration; existing orchestrator context; README and command reference.

## Required product outcome

Jarvis must support three user-visible capabilities:

1. Open the Spotify desktop application.
2. Play or pause the currently selected content locally.
3. Find and play a requested album or artist.

The third capability is inherently a provider decision: local desktop control can operate an already-running player, while discovery and reliable context playback require either Spotify Web API access or a desktop-specific URI/search mechanism. The change should not silently claim that one backend provides all three capabilities.

## Current repository evidence and gates

| Evidence | Finding | Consequence |
|---|---|---|
| `jarvis/src/jarvis/config.py` | `spotify` is already in `ALLOWED_APPS`; the app map in `actions/system.py` maps it to the `spotify` executable. | “Open Spotify” is largely an existing `open_app` path, subject to installed executable and the normal application allowlist. It is not yet a Spotify domain contract. |
| `jarvis/src/jarvis/interpreter/schema.py` | Current validated intents include `open_app`, `execute`, and other domains, but no media/Spotify intents. | New Spotify operations need explicit allowlisted intents/entities rather than relying on free-form `execute`. |
| `jarvis/src/jarvis/interpreter/golden.py` | `abrir ...` is a deterministic non-destructive fast path; unmatched requests go to the LLM; destructive intents are deterministic-only. | Spotify utterances should add narrow deterministic patterns where ambiguity or safety matters, while ordinary discovery may use the existing LLM fallback only if schema validation remains strict. |
| `jarvis/src/jarvis/actions/system.py` | `open_app` validates the app allowlist and starts a list-argument process without a shell. `execute` has a safe-binary allowlist and shell-operator blocklist, but it is still a generic command route with strict confirmation policy. | Spotify control MUST not be implemented as generated shell commands such as arbitrary `playerctl ...`; use a dedicated executor/backend adapter. |
| `jarvis/src/jarvis/actions/base.py` | Registry dispatches validated intents to in-process handlers; unknown intents are spoken as unsupported. | New handlers must be registered explicitly and receive only validated intents/entities. |
| `jarvis/src/jarvis/orchestrator/confirm.py` and config | Destructive actions and strict `execute` commands use the 15-second verbal confirmation lifecycle. | Play/pause/search/play are normally non-destructive and should not reuse the destructive confirmation gate. OAuth/device authorization is a separate external authorization prerequisite, not a spoken confirmation shortcut. |
| `jarvis/src/jarvis/orchestrator/loop.py` | Execution is followed by TTS/playback readiness handling and conversation follow-up; operation tokens and off precedence prevent stale work. | Spotify calls must be bounded, cancellable where possible, and must not dispatch late results after off/replacement. Long API calls may need the existing long-running acknowledgement path. |
| `openspec/specs/voice-pipeline/spec.md` | Mic remains closed during Jarvis playback and reopens only after the existing readiness barrier. | Do not conflate Spotify playback with Jarvis TTS playback; Spotify audio may continue after the spoken result and must not make Jarvis listen over its own voice. |
| README/manual | Spotify is documented only as an app that can be opened, not controlled. | Documentation and command help must not promise search/playback until a backend and failure semantics are specified. |

## Backend comparison

### Option A — local MPRIS / `playerctl`

**Shape:** invoke a dedicated local adapter around MPRIS, commonly through `playerctl`, targeting Spotify or the active player. Typical operations are status/play/pause/play-pause and metadata inspection. Search is not a portable MPRIS capability; playing a requested album/artist generally requires a Spotify URI/deep link, desktop UI automation, or a separate discovery provider.

**Strengths**

- Local control, no Spotify account token, client secret, or cloud API dependency.
- Low latency for current-content play/pause.
- Naturally fits the Linux/PipeWire desktop target and can control an already-authenticated Spotify desktop session.
- Keeps audio control separate from Jarvis's LLM and external data paths.

**Limitations and gates**

- `playerctl` is an external system dependency not currently represented in the app's dependency/configuration evidence; availability, bus access, player name, and Spotify MPRIS behavior must be diagnosed.
- MPRIS/playerctl cannot reliably search Spotify's catalog or select an arbitrary album/artist by name.
- “Current player” can accidentally target another MPRIS player unless the backend targets Spotify explicitly and validates the selected player.
- Subprocess calls must use list arguments, fixed verbs, bounded timeouts, and no shell. User text MUST never be interpolated into a command.
- Opening Spotify remains subject to the existing app allowlist; local control must not expand the arbitrary-shell surface.

**Best fit:** first slice for opening Spotify plus local play/pause/status/error reporting.

### Option B — Spotify Web API with OAuth

**Shape:** authenticate a Spotify user through Authorization Code with PKCE (preferred for a desktop/public client), store refresh/access token material in a local protected location, call catalog search for album/artist, then call playback endpoints using the selected Spotify URI. Playback control requires an available Spotify Connect device and, in practice, a Spotify Premium account for Web API playback control.

**Strengths**

- Catalog search has explicit album and artist semantics, IDs, names, images, and URIs.
- Search results can be disambiguated before starting playback.
- Playback API can target a known device and play a context URI rather than relying on UI state.
- Provides the only clearly specified route in this comparison for “find requested album or artist.”

**Limitations and gates**

- Requires user account authorization, redirect/PKCE flow, token refresh, secure local storage, scopes, expiry handling, and revocation/logout behavior.
- Requires network availability and external Spotify service availability; failures must be spoken without partial execution.
- Playback endpoints can fail because there is no active device, the device is unavailable, the account lacks Premium, or the requested context is not playable.
- Search terms and account metadata leave the local-only privacy posture described by the README; this is an explicit product/privacy change.
- Client credentials MUST NOT be committed or exposed in prompts/logs. OAuth state, redirect handling, and token files need a dedicated security design.
- OAuth authorization is not equivalent to Jarvis's 15-second destructive confirmation. It authorizes an account integration and should never be bypassed by `SAFETY_GATE=auto` or `yolo`.

**Best fit:** second slice for catalog search and context playback after OAuth and device policy are accepted.

### Recommended hybrid

Use MPRIS/playerctl for local current-content control and Spotify Web API for discovery/context selection. Keep the backend behind one Spotify domain service so the interpreter and registry do not expose backend-specific shell/API mechanics. Prefer the local path when a user asks to play/pause current content; use Web API only for explicit album/artist discovery/play requests. A later design must define whether Web API playback targets Spotify desktop, another Connect device, or a user-selected device.

A deep-link-only alternative (`spotify:album:...` / `spotify:artist:...`) is not sufficient as the primary design: it may open the client but does not guarantee playback, search by name, or deterministic device behavior. UI automation is rejected for the first slice because it is brittle, hard to test, and weakens the explicit-action boundary.

## Scope options

| Scope | Includes | Excludes | Assessment |
|---|---|---|---|
| S0 — reuse existing opening | Keep `open_app spotify`; document it as supported and diagnose executable. | Play/pause, search, OAuth. | Lowest risk, but does not satisfy the requested change alone. |
| S1 — local control first (recommended first slice) | Dedicated `spotify_play_pause` (or equivalent) intent, Spotify-targeted MPRIS/playerctl adapter, status/error handling, open Spotify prerequisite/fallback, bounded subprocess and off cancellation. | Catalog search, OAuth, arbitrary UI automation, playlist/track selection. | Smallest useful slice with no new cloud/privacy surface. |
| S2 — Web API discovery and playback | OAuth PKCE, token lifecycle, album/artist search, deterministic result selection or clarification, URI playback, device/Premium failures, secure config/storage. | General Spotify browsing, playlists/recommendations, arbitrary account mutation. | Satisfies full discovery requirement but carries the largest security and integration risk. |
| S3 — hybrid production feature | S1 + S2 behind a common service, backend selection, device policy, fallback behavior, docs/diagnostics. | Voice-controlled account management and UI automation. | Full target; should follow validated S1 and an explicit OAuth decision. |

## Dependencies and prerequisites

### Existing dependencies

- Linux desktop session with D-Bus/MPRIS support and Spotify desktop client for local control.
- `playerctl` installed and able to see the Spotify player, or an equivalent direct MPRIS implementation approved by design.
- Existing Jarvis wake/STT/interpreter/orchestrator/registry seams.
- Existing `spotify` app allowlist entry and installed `spotify` executable for open behavior.
- Existing `jarvis/.venv/bin/pytest` for later strict TDD; no test invocation is part of this exploration.

### New local dependencies to decide

- System package/runtime availability for `playerctl` versus a Python D-Bus/MPRIS library.
- Diagnostic checks and configuration for player name, timeout, and whether a missing player is recoverable.
- No new Python dependency is assumed until a spike measures subprocess versus D-Bus reliability.

### New Web API dependencies to decide

- Spotify developer application registration and redirect URI.
- PKCE-capable OAuth client implementation, HTTPS/network client, token persistence and secure permissions.
- Approved scopes, minimally `user-modify-playback-state` plus any scope required for the chosen search/playback flow; avoid unrelated account scopes.
- Device-selection policy and a clear Premium/active-device capability check.
- Local callback/redirect mechanism that does not expose a listening service beyond the authorization flow.

## Risks and mitigations

| Risk | Mitigation / decision needed |
|---|---|
| `playerctl` controls the wrong player | Target Spotify explicitly, verify player identity/metadata, and fail closed when no unique Spotify player exists. |
| Spotify is not running or MPRIS is unavailable | Return a spoken recoverable error; optionally offer/open Spotify, but do not pretend playback succeeded. |
| Search result ambiguity starts the wrong artist/album | Return a bounded list or ask for clarification; never choose solely from an untrusted fuzzy LLM extraction. |
| Web API playback changes an unintended device | Require explicit/default device policy, inspect available devices, and ask or fail when the target is ambiguous. |
| OAuth tokens leak into logs/history | Redact URLs/tokens, store with restrictive permissions, exclude secrets from `Session` history and spoken output. |
| Network/API latency blocks the voice loop | Use bounded timeouts, long-operation acknowledgement where needed, and operation-token cancellation before result dispatch. |
| `execute` becomes a backdoor for media commands | Do not add `playerctl` to `SAFE_BINARIES` for this feature; register dedicated intents only. |
| `SAFETY_GATE` semantics become confusing | Treat playback as non-destructive; keep destructive confirmation unchanged and keep OAuth consent as a separate one-time account gate. |
| Local-only privacy promise is weakened | Make Web API opt-in/configured, state data-sharing consequences, and preserve S1 as a functional local mode. |
| Desktop Spotify and Web API state diverge | Define source of truth and refresh/status behavior; hybrid backend must report which backend acted. |
| Audio playback is mistaken for Jarvis output | Preserve the existing TTS mic barrier and do not add barge-in or audio ducking in this change. |
| Platform assumptions break deployment | Limit first support to Linux/MPRIS and surface capability diagnostics; do not claim cross-platform support. |

## Assumptions

- The target environment is Linux Mint/Ubuntu with a graphical user session, matching the repository README.
- “Current content” means the content currently selected by a Spotify player, not arbitrary system audio.
- Play/pause is an explicit user command and does not require destructive confirmation.
- Album/artist requests mean catalog discovery followed by starting a playable context, not merely opening a Spotify URI.
- The first implementation may refuse ambiguous requests rather than inventing a selection.
- No Spotify credentials, developer application, or `playerctl` installation is currently established by repository evidence; those are prerequisites to validate, not implicit configuration.
- Existing off/non-vocal switch precedence, stale-operation invalidation, app allowlists, no-arbitrary-shell policy, and session privacy behavior remain binding.
- Later strict TDD covers deterministic intent/entity validation, fake local/API adapters, timeout/cancellation, OAuth redaction/lifecycle, and orchestrator/registry integration; this exploration intentionally defines no test list as an implementation task.

## Proposed first slice

**S1: local Spotify open + current-content play/pause via a dedicated backend.**

1. Confirm the host capability manually in a later spike: Spotify executable, `playerctl`, D-Bus session, visible Spotify player identity, and behavior when Spotify is absent.
2. Define a narrow domain contract for `spotify_play_pause` (and, if needed, a read-only status operation) with no raw command or arbitrary user argument.
3. Add a dedicated local adapter using fixed list-argument subprocess calls or approved D-Bus calls, bounded timeout, explicit Spotify targeting, and normalized success/failure results.
4. Route explicit Spanish play/pause variants through deterministic or schema-validated intent handling; reject ambiguous “play something” requests without executing.
5. Register the handler and thread it through existing operation/off/error/TTS seams; keep opening Spotify on the existing allowlisted `open_app` path, with any prerequisite opening behavior explicitly specified.
6. Add capability diagnostics and concise spoken errors, but defer OAuth and catalog search until the local contract is stable.

**Exit boundary:** S1 demonstrates opening Spotify and controlling the current Spotify content locally without `execute`, without OAuth, without arbitrary shell, without UI automation, and without changing destructive confirmation semantics. S2 should begin only after a product decision accepts external Spotify API data, OAuth storage, required scopes, Premium/device constraints, and the result-disambiguation UX.

## Open decisions for proposal/design

1. Should “abrir Spotify” remain the existing `open_app` command, or gain a Spotify-specific intent that can report readiness?
2. Should play/pause target Spotify only, or the active MPRIS player when Spotify is unavailable?
3. Should a play/pause request open Spotify automatically when it is not running, or fail and ask the user to open it?
4. For Web API playback, should Jarvis require Premium and an active device, ask the user to choose among devices, or use a configured default?
5. What OAuth flow and local secret storage are acceptable, and is Web API explicitly opt-in to preserve the local-only default?
6. When album/artist search returns multiple plausible results, should Jarvis speak a short numbered clarification or require a more specific request?
7. Should Web API search be permitted to play through the desktop client only, or any Spotify Connect device?

## Rollback and handoff

Keep Spotify behavior behind a dedicated registry/service seam and a feature/capability switch. If local control is unreliable, disable the dedicated intents while retaining the existing allowlisted `open_app spotify` behavior. If OAuth security or privacy gates are not accepted, ship S1 only and do not add Web API credentials, scopes, or network calls. Never fall back from a failed validated Spotify operation to generated shell execution or an unconfirmed destructive route.

Next phase: proposal clarification using the seven open decisions, followed by a design that fixes the local backend contract, OAuth boundary, device policy, and exact interpreter/registry seams before implementation tasks are created.

## Stage 0 capability spike (provider-authorized work unit)

### Host probe boundary and exact commands

All probes in this section were read-only. No package installation, Spotify launch, D-Bus method with side effects, subprocess mutation, production source edit, test edit, configuration edit, OAuth action, or credential access was performed.

Commands run from `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`:

```text
command -v playerctl
playerctl --version
playerctl -l
command -v spotify
pgrep -x -a spotify
busctl --user list | grep -iE 'org\\.mpris|spotify'
dbus-send --session --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames
busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2
```

Observed results:

| Probe | Result | Exit status / implication |
|---|---|---|
| `command -v playerctl` | No executable found | `1`; the local playerctl backend is unavailable on this host. |
| `playerctl --version` | `orden no encontrada` | `127`; no playerctl command can be issued. |
| `playerctl -l` | `orden no encontrada` | `127`; no empirical player listing is possible through playerctl. |
| `command -v spotify` | `/usr/bin/spotify` | `0`; the existing Spotify launch executable is present. |
| `pgrep -x -a spotify` | No process listed | `1`; Spotify Desktop was not running during the probe. |
| user-bus MPRIS/Spotify name filter | No matching name | `1`; no uniquely visible Spotify MPRIS identity was observed. |
| D-Bus `ListNames` | Session bus answered; no matching MPRIS/Spotify name was returned | Read-only session-bus access is available, but no Spotify identity was present. |
| `busctl --user introspect org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2` | `The name org.mpris.MediaPlayer2.spotify was not provided by any .service files` | `1`; the expected Spotify MPRIS service is absent. |

At the time of this initial probe, the host had the existing Spotify executable and a user D-Bus session but did not provide the prerequisite `playerctl` binary, running Spotify process, or Spotify MPRIS name. That historical result was `capability_unavailable`, not proof that Spotify MPRIS is incompatible.

### Superseding live capability evidence

After the user installed `playerctl` and opened Spotify, the following read-only live results were obtained from `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`:

| Probe | Result | Implication |
|---|---|---|
| `playerctl --version` | `playerctl v2.4.1` | The required local capability tool is installed. |
| `playerctl -l` | Exactly `spotify` | One uniquely identified Spotify MPRIS player is visible; no active-player fallback is needed. |
| `playerctl --player=spotify status` | `Playing` | The fixed Spotify-targeted status command succeeds against the live player. |
| Metadata query | `spotify\|Personalmente\|Las Pelotas` | The live target reports Spotify metadata for the currently selected content. |

These results validate unique Spotify MPRIS detection and fixed player targeting for the Stage 1 contract. They do not validate a mutating control action: no `play` or `pause` command was invoked, and no production code, tests, configuration, OAuth material, credentials, or dependencies were changed. Post-action state verification therefore remains an implementation requirement rather than an observed result.

### Fixed command and identity contract

The adapter contract is deliberately narrower than generic `safe_run` and is not an implementation change in this spike:

| Probe/action | Fixed argv | Expected success | Safe failure interpretation |
|---|---|---:|---|
| capability listing | `playerctl`, `-l` | `0`, parse identities | `127` missing binary; nonzero means capability unavailable |
| identity/status verification | `playerctl`, `--player=spotify`, `status` | `0` and Spotify identity/state | nonzero or identity mismatch means fail closed |
| play | `playerctl`, `--player=spotify`, `play` | `0`, then bounded status verification | nonzero or unverifiable state means control failed/state unknown |
| pause | `playerctl`, `--player=spotify`, `pause` | `0`, then bounded status verification | nonzero or unverifiable state means control failed/state unknown |

`spotify` is the default exact MPRIS identity spelling from the design. Identity matching may normalize only the approved case convention, must not use the active/current-player fallback, and must require exactly one matching player. A zero match, multiple matches, absent D-Bus service, missing binary, timeout, or identity mismatch is unavailable/ambiguous and must not control another player.

The subprocess boundary must use a fixed list argv, explicit `shell=False`, captured output, a bounded timeout, and redacted diagnostics. User transcript/entity data must not contribute an argument. The current repository `jarvis.actions.base.safe_run` uses list arguments and the default non-shell subprocess behavior, but collapses missing-binary/timeout failures to code `1` and returns stderr; the Spotify adapter should therefore own typed normalization rather than expose that helper's raw result as a domain result.

A successful control command is not sufficient evidence of playback. The adapter must perform a separate bounded status check and return success only when the requested state is known. It cannot establish uninterrupted audio, track selection, catalog search, or eventual playback beyond the observed MPRIS status; those remain post-action limits. The absent host capability means no post-action status was available in this spike.

### Injected seams and rollout decision

Before source implementation, the smallest reusable boundary is:

- `Runner.run(argv: list[str], *, timeout_s: float) -> CompletedResult`, with an injected fake recording exact argv, timeout, and shell-disabled policy; production calls use fixed argv only.
- `Clock.now() -> float`, injected for capability-cache expiry and deterministic bounded status verification.
- `OperationToken.cancel(reason)` / `cancelled()` / current-generation validation, checked before probe, before control, and before returning; stale results must not speak or create a late side effect.
- Trusted configuration loaded outside voice entities: `SPOTIFY_PLAYERCTL_BIN` (default `playerctl`, validated trusted executable value), `SPOTIFY_MPRIS_IDENTITY` (default `spotify`, validated identifier grammar and never transcript-controlled), and bounded local/status timeouts. Invalid values fail closed rather than being repaired from user input.
- A typed capability result distinguishing `binary_missing`, `mpris_unavailable`, `identity_missing`, `identity_ambiguous`, `timeout`, `control_failed`, `state_unknown`, `cancelled`, and `stale`; raw stderr and arbitrary argv do not cross the domain boundary.

The repository already provides compatible patterns: `jarvis.orchestrator.contracts.OperationToken`, injectable `Clock` protocols, and `jarvis.actions.base.safe_run`'s list-argument/no-shell convention. This spike intentionally does not modify those production seams.

**Rollout decision:** an unavailable host capability does not block rolling out the dedicated Stage 1 code contract, but it blocks advertising or enabling local control on this host. Runtime behavior must remain fail-closed with an accurate recoverable error, while the existing allowlisted `open_app spotify` behavior remains available. Stage 1 acceptance requires a later host with `playerctl`, a live Spotify MPRIS service, and a uniquely matching identity; no fallback player, shell route, automatic Spotify launch, or OAuth/API dependency is permitted.

### Strict-TDD evidence and task record

This is a documentation-only Stage 0 spike, so the required project test command was intentionally not run:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
```

Running it would not validate the host capability or the documentation-only seam without writing RED tests and production implementation, both outside this authorized work unit. Deterministic fake/contract evidence is therefore deferred to Stage 1, where RED must assert exact argv, timeout propagation, zero/one/multiple identity states, and cancellation; GREEN must implement the smallest adapter; TRIANGULATE must compare those fakes with an opt-in live Linux probe; REFACTOR must preserve the seam and fail-closed policy. The read-only probe above is the only host evidence and validates capability absence plus the need for injected seams; it does not claim adapter correctness or hardware/provider acceptance.

The authorized Stage 0 work-unit record is:

- [x] 0.1.1 Inspect host `playerctl`/D-Bus/MPRIS/Spotify identity and document fixed command behavior, identity, exit codes, and post-action limits.
- [x] 0.1.2 Define injected runner/clock/operation-token/trusted config seams and decide rollout behavior for unavailable capability.

No Stage 1 or Stage 2 artifact, source file, test, configuration, OAuth material, credential, or dependency was changed.
