# Spotify Control Specification

## Purpose

Define safe, explicit control of Spotify Desktop on this PC in two stages: credential-free local MPRIS control, followed by an explicitly authorized official Spotify integration for album and artist search and playback.

## Requirements

### Requirement: Preserve the existing Spotify application launch boundary

The system MUST preserve the existing `open_app` behavior and application allowlist when opening Spotify. Spotify control MUST NOT broaden application launching or generic command execution.

#### Scenario: Existing Spotify launch request

- GIVEN the user makes an existing supported request to open Spotify
- WHEN the request is executed
- THEN the system MUST use the existing allowlisted `open_app` behavior
- AND MUST open only the allowlisted Spotify application

#### Scenario: Disallowed launch or shell request

- GIVEN a request names an unallowlisted application or includes arbitrary shell arguments
- WHEN the request is interpreted
- THEN the system MUST reject it
- AND MUST NOT launch the application or execute a shell command

### Requirement: Stage 1 provides Spotify-only local play and pause

When Stage 1 is available, the system MUST provide explicit play and pause actions for content already loaded in Spotify Desktop through Spotify's local MPRIS player. Stage 1 MUST require neither Spotify credentials nor network access.

#### Scenario: Local play or pause succeeds

- GIVEN Spotify Desktop is uniquely identified as the local Spotify MPRIS player
- AND content is loaded in Spotify Desktop
- WHEN the user requests play or pause in Stage 1
- THEN the system MUST apply only that requested action to Spotify Desktop on this PC
- AND MUST report the resulting action accurately

#### Scenario: Stage 1 works offline and without credentials

- GIVEN the machine has no network access and no Spotify OAuth credentials
- AND Spotify Desktop exposes its local Spotify MPRIS player
- WHEN the user requests local play or pause
- THEN the system MUST attempt the local action
- AND MUST NOT request credentials or make a network call

#### Scenario: No uniquely controllable Spotify player

- GIVEN Spotify Desktop is unavailable, its local MPRIS capability is missing, or the Spotify identity is absent or ambiguous
- WHEN the user requests Stage 1 play or pause
- THEN the system MUST fail closed
- AND MUST provide a spoken recoverable error
- AND MUST NOT control another MPRIS player or claim success

### Requirement: Spotify actions MUST use a validated domain boundary

Spotify actions MUST be represented and validated as narrow Spotify capabilities. They MUST NOT route through generic `execute`, arbitrary shell execution, browser automation, or caller-supplied command arguments.

#### Scenario: Narrow Spotify action

- GIVEN the interpreter receives a supported Spotify play or pause request
- WHEN the action is dispatched
- THEN it MUST dispatch only the validated Spotify action and its permitted entity data
- AND MUST NOT expose a generic command or shell interface

#### Scenario: Unsupported media operation

- GIVEN the user requests playlists, recommendations, arbitrary track selection, or control of a non-Spotify player
- WHEN the request is evaluated
- THEN the system MUST reject it as unsupported
- AND MUST NOT perform an alternate media action

### Requirement: Stage 2 requires explicit official OAuth opt-in

Stage 2 MUST remain disabled until the user explicitly opts in and completes the official Spotify OAuth authorization. Stage 1 MUST NOT silently enable OAuth, transmit Spotify account data, or depend on Stage 2 configuration.

#### Scenario: OAuth is not enabled

- GIVEN the user has not explicitly opted in or has not completed authorization
- WHEN the user requests Stage 2 search or playback
- THEN the system MUST not call the Spotify Web API
- AND MUST explain that explicit authorization is required
- AND MUST leave Stage 1 behavior unchanged

#### Scenario: OAuth is explicitly authorized

- GIVEN the user has opted in and completed official Spotify authorization
- WHEN the integration is enabled
- THEN Stage 2 catalog operations MAY be available
- AND the system MUST use only the approved minimum scope set required for album and artist search and playback

### Requirement: OAuth credentials MUST be protected and redacted

The system MUST store access and refresh tokens using protected local storage, MUST handle expiry or refresh and disable/revoke operations, and MUST redact tokens and authorization material from logs, history, prompts, and spoken or displayed responses.

#### Scenario: Token material is not disclosed

- GIVEN an OAuth flow, API response, refresh, error, or diagnostic contains token or authorization material
- WHEN the system records or presents its result
- THEN the material MUST be absent or irreversibly redacted from logs, history, prompts, TTS, and user-visible diagnostics

#### Scenario: Expired, revoked, or disabled authorization

- GIVEN authorization is expired, revoked, invalid, or disabled
- WHEN a Stage 2 operation is requested
- THEN the system MUST not perform unauthorized API or playback activity
- AND MUST report that reauthorization or enablement is required

### Requirement: Stage 2 MUST search the official Spotify catalog for albums and artists

After authorization, Stage 2 MUST use the official Spotify catalog for supported album and artist searches. Search results MUST be presented without playback until the requested result is unambiguous.

#### Scenario: Unambiguous catalog result

- GIVEN an authorized user requests a supported album or artist search
- AND exactly one plausible result is available
- WHEN the result is presented
- THEN the system MAY proceed with that clarified album or artist context
- AND MUST NOT select an unrelated result

#### Scenario: Multiple plausible results require clarification

- GIVEN an authorized search returns multiple plausible albums or artists
- WHEN the results are presented
- THEN the system MUST ask the user for spoken clarification
- AND MUST NOT automatically rank, choose, or play any result

#### Scenario: No result or unavailable catalog

- GIVEN the official catalog returns no supported result, the network/API is unavailable, or the request cannot be completed
- WHEN the search finishes
- THEN the system MUST provide a clear recoverable error
- AND MUST NOT claim a result or begin playback

### Requirement: Stage 2 playback MUST target Spotify Desktop on this PC only

Stage 2 playback MUST use the clarified album or artist context and MUST target Spotify Desktop on this PC. The system MUST NOT switch devices, control another player, use Spotify Connect as a fallback, or fall back to another playback device or application.

#### Scenario: Authorized Premium playback succeeds

- GIVEN the user is authorized, has a Premium account, the requested context is clarified and playable, and Spotify Desktop on this PC is the configured target
- WHEN the user confirms or requests playback
- THEN the system MUST start playback only through that Spotify Desktop target
- AND MUST report success only when the playback result is known

#### Scenario: Premium requirement is not met

- GIVEN the authorized Spotify account is not Premium
- WHEN the user requests Stage 2 playback
- THEN the system MUST explain that Premium is required
- AND MUST NOT attempt alternate playback

#### Scenario: Desktop target or content is unavailable

- GIVEN Spotify Desktop on this PC is unavailable, unauthorized as a target, the content is unplayable, or the playback result is unknown
- WHEN Stage 2 playback is requested
- THEN the system MUST fail closed with a clear spoken error
- AND MUST NOT switch to another device or player
- AND MUST NOT claim playback succeeded

### Requirement: Spotify operations MUST preserve existing safety and lifecycle gates

Spotify operations MUST preserve existing cancellation, operation-freshness, `off` precedence, conversation handling, TTS/microphone safety barriers, and existing destructive confirmations. Cancellation, `off`, stale results, or an unavailable readiness barrier MUST prevent a pending Spotify operation from executing or reporting success.

#### Scenario: Cancellation or off invalidates a pending operation

- GIVEN a Spotify operation is pending or an external request is in flight
- WHEN cancellation or the assistant's `off` control occurs
- THEN the operation MUST be invalidated
- AND any late result MUST NOT control Spotify or claim success

#### Scenario: Existing confirmation and open-app behavior remain unchanged

- GIVEN an existing destructive action or supported `open_app` request is processed alongside the new Spotify capability
- WHEN its existing gate is evaluated
- THEN the existing confirmation, allowlist, and lifecycle behavior MUST continue to apply
- AND Spotify capability MUST NOT bypass or weaken those gates
