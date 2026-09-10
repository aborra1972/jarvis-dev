# Proposal: Spotify Desktop Control in Two Stages

## Intent

Extend Jarvis with safe, explicit voice control for Spotify Desktop on this PC. The change addresses the gap between the existing ability to open Spotify and the user's need to control currently loaded Spotify content locally, while reserving catalog search and requested album/artist playback for an explicitly authorized Spotify integration.

The proposal deliberately separates the local, privacy-preserving capability from the networked OAuth capability so Stage 1 remains useful without account integration and Stage 2 cannot silently expand Jarvis's data or device-control boundary.

## Confirmed Product Decisions

- Delivery is split into two stages.
- The playback target is Spotify Desktop on this PC.
- Stage 1 provides Spotify Desktop local opening plus Spotify-only MPRIS play/pause of loaded content.
- Stage 2 is opt-in official Spotify OAuth for album/artist search and playback.
- OAuth uses the minimum scopes required by the approved functionality.
- Spotify Web API playback requires a Premium account.
- OAuth tokens must be stored safely and must not appear in logs, history, prompts, or spoken output.
- Multiple search results MUST require spoken clarification; Jarvis MUST never choose a result automatically.
- Existing safety gates and existing `open_app` behavior remain unchanged.
- No arbitrary shell, browser automation, fallback to another player/device, or implicit device switching is permitted.

## Scope

### Stage 1 — Local Spotify Desktop control

In scope:

- Preserve the existing allowlisted `open_app` behavior for opening Spotify.
- Add an explicit Spotify-only local play/pause capability for content already loaded in Spotify Desktop.
- Use a dedicated, validated Spotify domain action rather than exposing shell commands or accepting arbitrary command arguments.
- Target Spotify's MPRIS player specifically and fail closed if Spotify cannot be uniquely identified or controlled.
- Report unavailable Spotify, missing local MPRIS capability, and failed control as spoken recoverable errors; never claim success when playback state is unknown.
- Preserve existing off/cancellation behavior, operation freshness, conversation handling, and TTS/microphone safety barriers.

Out of scope:

- Catalog search, album/artist selection, playlists, recommendations, or arbitrary track selection.
- Spotify OAuth, network calls, account data, or token storage.
- UI/browser automation and control of non-Spotify MPRIS players.

### Stage 2 — Opt-in official Spotify OAuth

In scope:

- An explicit opt-in integration using Spotify's official OAuth flow.
- Minimum approved scopes only, with the final scope set limited to the required album/artist search and playback operations.
- Secure local access/refresh token storage, redaction, expiry/refresh handling, and a way to disable or revoke the integration.
- Official Spotify catalog search for albums and artists.
- Spoken presentation of multiple plausible results and mandatory clarification before any selection or playback.
- Playback of the clarified album/artist context through the configured Spotify Desktop target on this PC.
- Clear handling for unauthenticated users, revoked/expired authorization, unavailable network/API, non-Premium accounts, unavailable desktop target, and unplayable content.

Out of scope:

- Any fallback to another player or Spotify Connect device.
- Automatic result ranking/selection when multiple results exist.
- Browser automation, arbitrary account mutations, playlists/recommendations, or general Spotify account management.
- Silent enablement of OAuth or transmission of Spotify data in the local-only mode.

## Affected Areas

- **Command interpretation:** new narrow Spotify actions and entities must be validated and must not route through generic `execute`.
- **Action dispatch:** a dedicated Spotify domain handler/service boundary will connect voice intents to local MPRIS or official API operations.
- **System integration:** Stage 1 depends on the host's Spotify Desktop MPRIS presence while retaining the current application allowlist and launch semantics.
- **Configuration and diagnostics:** capability, opt-in status, Premium/API readiness, and local failure states need explicit reporting without exposing secrets.
- **Orchestration and lifecycle:** bounded operations, stale-result cancellation, off precedence, and spoken error handling must follow existing behavior.
- **Privacy and security:** Stage 2 introduces an explicit external-data and credential boundary; tokens and authorization material require protected storage and redaction.
- **User documentation:** supported commands, Stage 1/Stage 2 boundaries, OAuth consent, Premium requirement, and mandatory clarification behavior must be documented.

## Product Behavior and Success Criteria

- [ ] Saying an existing supported open-app request for Spotify preserves current `open_app` behavior and opens only the allowlisted Spotify application.
- [ ] A local play/pause request affects Spotify Desktop's loaded content only, or fails closed with an accurate spoken explanation.
- [ ] Stage 1 works without Spotify credentials, OAuth, or network access.
- [ ] Stage 1 never invokes arbitrary shell commands and never controls another player.
- [ ] Stage 2 remains disabled until the user explicitly opts in and completes official OAuth authorization.
- [ ] OAuth requests only the minimum approved scopes, and stored tokens are protected and absent from logs/history/spoken responses.
- [ ] Album and artist searches can return results without playback until the requested result is unambiguous.
- [ ] Whenever multiple plausible results exist, Jarvis asks for spoken clarification and performs no automatic selection.
- [ ] Stage 2 playback targets Spotify Desktop on this PC only; it does not switch to or fall back to another device/player.
- [ ] Non-Premium accounts and unavailable/unauthorized Spotify targets receive clear failure responses without partial or alternate execution.
- [ ] Existing destructive confirmations, safety gates, `open_app` semantics, off behavior, and no-arbitrary-shell guarantees remain unchanged.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Local control reaches the wrong media player | Require an explicit Spotify MPRIS identity and fail closed when it is absent or ambiguous. |
| Spotify is closed or MPRIS is unavailable | Return a recoverable spoken error; retain the existing explicit open-app path without pretending playback succeeded. |
| A search selects the wrong artist or album | Make clarification mandatory for multiple results; never let fuzzy matching or the LLM choose automatically. |
| OAuth tokens or account data leak | Use protected local storage, strict redaction, and no secret/account material in history, logs, prompts, or TTS. |
| API playback is unavailable for the account or desktop client | Check authorization, Premium eligibility, API/device availability, and target identity; fail without another-device fallback. |
| New media functionality becomes a shell backdoor | Use dedicated validated actions and keep `playerctl`/equivalent mechanics out of generic shell execution. |
| External calls degrade the voice loop | Bound network operations, preserve cancellation/off precedence, and report delayed or failed operations accurately. |
| Local privacy expectations are weakened | Keep Stage 1 fully local and make all Stage 2 network/account behavior opt-in and visible. |

## Rollback Plan

- Disable or remove the dedicated Spotify control capability while retaining the existing allowlisted `open_app` Spotify behavior.
- If the local backend is unreliable, turn off Stage 1 control without changing generic system actions.
- If OAuth, scope, storage, privacy, Premium, or desktop-target requirements are not acceptable, ship or retain Stage 1 only and remove Stage 2 authorization/configuration without affecting local control.
- Revoke the Spotify authorization and delete protected token material when rolling back Stage 2.
- Never roll back by enabling generic shell execution, browser automation, another player, or another device as a substitute.

## Delivery Boundary

This proposal covers the product intent and two-stage scope only. Detailed requirements, architecture, implementation tasks, and test planning belong to subsequent OpenSpec phases and are intentionally not included here.

## SDD Result Contract

- **phase:** proposal
- **change:** `jarvis-spotify-control`
- **status:** completed
- **artifact:** `openspec/changes/jarvis-spotify-control/proposal.md`
- **skill_resolution:** fallback-path
- **artifact_store:** openspec
- **next_phase:** spec
- **code_changed:** none
- **out_of_scope_artifacts:** spec, design, tasks, and implementation
