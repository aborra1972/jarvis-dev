# Apply Progress: `jarvis-spotify-control`

## SDD Result Contract

- **phase:** apply
- **change:** `jarvis-spotify-control`
- **status:** completed
- **artifact_store:** openspec
- **skill_resolution:** fallback-path
- **work_unit:** provider-authorized Stage 0 reconciliation only
- **code_changed:** none
- **next_phase:** verify

## Scope and safety boundary

This apply was documentation-only and read-only with respect to the host capability probe. No production source, tests, configuration, OAuth material, credentials, dependency manifests, or Stage 1/Stage 2 tasks were changed. The allowed edit scope was limited to:

- `openspec/changes/jarvis-spotify-control/tasks.md`
- `openspec/changes/jarvis-spotify-control/apply-progress.md`
- `openspec/changes/jarvis-spotify-control/exploration.md`

The forecasted full feature remains a high-risk, chained delivery. This work unit does not authorize or begin that implementation; it is independently bounded to reconciling the two completed Stage 0 spike rows.

## Completed tasks and persisted checkbox updates

- [x] 0.1.1 — Host `playerctl`/D-Bus/MPRIS/Spotify identity probe and fixed command/identity/exit-status/post-action limitation record. Persisted as checked in `tasks.md`.
- [x] 0.1.2 — Injected runner, clock, operation-token, trusted configuration seams, and unavailable-capability rollout decision. Persisted as checked in `tasks.md`.

The corresponding initial evidence is recorded in `exploration.md`: `playerctl` was absent (`command -v` exit `1`; attempted invocations exit `127`), Spotify's executable was present, Spotify Desktop was not running, no Spotify MPRIS identity was visible, and the expected D-Bus service was absent at that time. The later live evidence below supersedes the capability-absence finding; it still does not establish post-action playback verification.

## Rollout decision

The earlier rollout decision was `capability_unavailable`; the later live probe now confirms the prerequisite tool and a unique Spotify MPRIS identity. This documentation update does not authorize enabling or advertising implemented local control: any implementation must still fail closed, perform post-action verification, and preserve the existing allowlisted `open_app spotify` behavior. No fallback player, generic shell route, automatic launch, OAuth, or API dependency is authorized.

## Test and evidence status

No project test command was run:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
```

Tests remain deferred because this authorized work unit only reconciled a documented, side-effect-free capability probe and seam decision. Running strict-TDD RED/GREEN tests would require the subsequent Stage 1 implementation boundary, which is explicitly out of scope. The deterministic fake/contract RED evidence for exact argv, timeout propagation, identity cardinality, and cancellation remains a Stage 1 prerequisite; the live Linux/playerctl results below are capability evidence only, not implementation or playback-control acceptance.

## Files changed

- `openspec/changes/jarvis-spotify-control/tasks.md` — marked only Stage 0 rows 0.1.1 and 0.1.2 complete.
- `openspec/changes/jarvis-spotify-control/exploration.md` — reconciled the header to record the completed documentation-only spike.
- `openspec/changes/jarvis-spotify-control/apply-progress.md` — recorded scope, evidence, deferred tests, and fail-closed rollout decision.

## Superseding live capability evidence

A later provider-authorized, read-only probe supersedes the earlier absence finding after the user installed `playerctl` and opened Spotify. The live results were:

- `playerctl --version` returned `playerctl v2.4.1`.
- `playerctl -l` returned exactly `spotify`.
- `playerctl --player=spotify status` returned `Playing`.
- Metadata reported `spotify|Personalmente|Las Pelotas`.

This validates unique Spotify MPRIS detection and fixed `--player=spotify` targeting for the Stage 1 capability contract. No `play` or `pause` command was invoked. No production code, tests, configuration, OAuth material, credentials, or dependencies were changed. Post-action verification remains unmeasured and stays an implementation requirement.

## Documentation-only update

- `openspec/changes/jarvis-spotify-control/exploration.md` — retained the original absence probe as historical context and added the superseding live capability evidence.
- `openspec/changes/jarvis-spotify-control/apply-progress.md` — recorded the new live results and preserved the documentation-only boundary.
- `openspec/changes/jarvis-spotify-control/tasks.md` — not changed; the two Stage 0 rows remain checked and all implementation rows remain unchecked.

## Remaining tasks

All Stage 1 and Stage 2 implementation-owned task rows remain unchecked and untouched. No implementation task was started by this work unit.

## Verification notes

Before return, the persisted task artifact was re-read and confirmed to show exactly the two Stage 0 rows as `[x]`; all later task rows remain `[ ]`. No archived first-slice artifact, production surface, test surface, credentials, or dependency surface was changed.

## Stage 1 apply: authorized work unit `spotify-stage1-intents-config`

- **Scope:** Implemented only task rows 1.1.1 and 1.1.2. No MPRIS adapter, service, registry, lifecycle, diagnostics, OAuth, or documentation work was performed.
- **Persisted tasks:** The two selected rows are `[x]` in `tasks.md`; all other implementation rows remain `[ ]` and untouched.
- **Files changed:** `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/golden.py`, `jarvis/src/jarvis/config.py`, `jarvis/tests/unit/test_schema.py`, `jarvis/tests/unit/test_golden.py`, and `jarvis/tests/unit/test_config.py`.
- **Behavior:** Added separate schema-validated `SPOTIFY_INTENTS` for entity-free `spotify_play`/`spotify_pause`, exact Spotify-targeted Spanish golden forms, and fail-closed local settings validation. Existing `ALLOWED_APPS`, `open_app`, generic `execute`, OAuth absence, and unrelated domains remain unchanged.
- **Workload boundary:** 128 authored changed lines in the selected source/test surfaces, below the requested 350-line limit. Unrelated pre-existing `.atl` working-tree changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Focused tests were added first; the focused run reported 12 failures for missing Spotify intents, patterns, and config loader. |
| GREEN | Minimal implementation made the focused suite pass: `264 passed`. |
| TRIANGULATE | Required full command passed offline: `1032 passed, 1 warning`; the warning is the existing unknown `e2e` mark. Existing registry, `open_app`, `execute`, and regression tests passed. |
| REFACTOR | Spotify intents remain a separate schema allowlist so the not-yet-authorized service/registry work unit stays untouched; exact matching and fail-closed defaults were retained. |

### Remaining tasks

Exact unchecked implementation rows remain persisted in `tasks.md`, beginning with:

- [ ] Create the Spotify local adapter/service boundary at concrete targets `jarvis/src/jarvis/services/spotify.py` and, if needed, a focused subprocess module under `jarvis/src/jarvis/services/`; add unit tests under `jarvis/tests/unit/test_spotify_local.py` using fake runners. <!-- sdd-owner: implementation -->
- [ ] Add the Stage 1 service dispatch and registry wiring in `jarvis/src/jarvis/actions/base.py` plus focused tests in `jarvis/tests/unit/test_spotify_service.py` and `jarvis/tests/unit/test_actions_base.py`. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 1 lifecycle handling with `jarvis/src/jarvis/orchestrator/loop.py` and `jarvis/src/jarvis/orchestrator/contracts.py`. <!-- sdd-owner: implementation -->
- [ ] Extend `jarvis/src/jarvis/diagnose.py` with safe local Spotify capability diagnostics and document Stage 1 commands/boundaries. <!-- sdd-owner: implementation -->
- [ ] Run a Stage 1 acceptance pass with no network and no Spotify credentials. <!-- sdd-owner: implementation -->
- [ ] Complete all later Stage 2 OAuth, catalog, playback, documentation, and release-verification rows only under separately authorized work units. <!-- sdd-owner: implementation -->

**Structured status consumed:** `applyState: ready`, `actionContext.mode: repo-local`, workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`, allowed edit roots include the workspace, and the parent explicitly resolved the high-risk forecast by authorizing this bounded Stage 1 work unit. **Next phase:** `sdd-verify`.

## Stage 1 task 1.2.1 — Spotify-only local MPRIS adapter

- **Status:** completed; only the adapter task was authorized and marked `[x]` in `tasks.md`. Registry/dispatch, lifecycle, diagnostics, documentation, OAuth, and Stage 2 remain untouched.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_local.py`, and the selected checkbox in `tasks.md`.
- **Behavior:** `LocalSpotifyAdapter` uses fixed list/status/play/pause argv with `shell=False` and bounded timeout; it requires exactly one exact configured Spotify identity, checks `OperationToken` cancellation before probe/control/return, verifies post-action state, and returns typed safe categories without stderr or command detail. It accepts no user command arguments and performs no network/OAuth.
- **Workload:** 245 authored changed lines across the source/test/task slice, below the requested 350-line limit; unrelated working-tree changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added `jarvis/tests/unit/test_spotify_local.py` first; collection failed because `jarvis.services.spotify` did not exist. The tests cover exact argv and subprocess flags, bounded timeout, missing binary, timeout, nonzero control, zero/one/multiple identity, cancellation, redaction, and unknown post-state. |
| GREEN | Implemented the smallest fixed-command adapter; focused tests passed: `7 passed`. |
| TRIANGULATE | Required offline command passed: `1039 passed, 1 warning` using `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q`; the warning is the existing unknown `e2e` mark. Fake-runner traces confirm no control command occurs without unique Spotify identity and no success is returned for unknown state or cancellation. No host probe, network, credentials, or OAuth was used. |
| REFACTOR | Added cancellation checks after each subprocess boundary, kept fixed argv construction inside the adapter, isolated safe result categories/messages, and left registry/loop/diagnostic surfaces unchanged. |

### Remaining implementation tasks

All other implementation-owned task rows remain unchecked and were not edited, including the Stage 1 service dispatch/registry, lifecycle, diagnostics, acceptance, and all Stage 2 rows.

## Correction work unit `spotify-mpris-probe-failclosed-correction`

- **Scope:** Corrected only the verifier blocker in the completed Stage 1 local adapter slice. A nonzero `playerctl -l` probe now returns `MPRIS_UNAVAILABLE` before stdout identity parsing, so control is never invoked regardless of probe output.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_local.py`, and this progress evidence only. No task checkbox was changed because the parent adapter task was already checked; all unrelated working-tree changes were preserved.
- **Safety preserved:** Fixed argv, `shell=False`, bounded timeout, identity filtering, and all existing behavior remain unchanged.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added `test_nonzero_probe_with_spotify_output_fails_closed_without_control`; focused test failed because stdout was trusted and returned `IDENTITY_MISSING` rather than failing at the probe boundary. |
| GREEN | Added the minimal nonzero-probe guard returning `MPRIS_UNAVAILABLE`; focused adapter tests passed: `8 passed`. |
| TRIANGULATE | Required command passed: `1040 passed, 1 warning`; the warning is the existing unknown `e2e` mark. The fake trace contains only `playerctl -l` and no play/pause invocation. |
| REFACTOR | Reviewed the correction as a three-line guard at the existing probe seam; no broader refactor or behavior change was warranted. |

**Required command:** `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q`

**Remaining scope:** No additional task was authorized by this correction work unit. The existing later implementation-owned rows remain unchecked and out of scope.

## Stage 1 task 1.2.2 — dedicated Spotify service dispatch

- **Status:** completed; only task 1.2.2 was authorized and marked `[x]` in `tasks.md`. Lifecycle, diagnostics, documentation, OAuth, network, credentials, dependencies, schema, configuration, loop, and contracts remain untouched.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py` (minimal additive service boundary), `jarvis/src/jarvis/actions/base.py`, `jarvis/tests/unit/test_spotify_service.py`, `jarvis/tests/unit/test_actions_base.py`, and the selected checkbox in `tasks.md`.
- **Behavior:** `SpotifyService` accepts only entity-free `spotify_play` and `spotify_pause`, routes directly to `LocalSpotifyAdapter`, maps typed failures to safe recoverable speech, and refuses success for unknown or malformed outcomes. Registry handlers are dedicated and do not route through `system.execute`; existing `open_app` and generic `execute` registrations are unchanged.
- **Workload:** 159 authored changed/added lines across the selected implementation, test, and OpenSpec surfaces, below the requested 350-line limit. Pre-existing `.atl` changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added `jarvis/tests/unit/test_spotify_service.py` and registry isolation assertions first; collection failed because `SpotifyService` was absent, then the focused registry expectation failed because the new schema-allowlisted intents were not yet registered. |
| GREEN | Added the minimal service and two dedicated registry registrations, then updated the stale coverage expectation; focused tests passed: `17 passed`. |
| TRIANGULATE | Required command passed offline: `1046 passed, 1 warning`; fake adapter traces prove only validated Spotify intents call the adapter, failure details are not spoken, unknown state cannot succeed, and existing registry tests pass. The warning is the existing unknown `e2e` mark. |
| REFACTOR | Kept the service in the existing `services/spotify.py` boundary, used fixed intent names/entity rejection, centralized safe error speech, and left generic execution, `open_app`, lifecycle, diagnostics, and configuration behavior unchanged. |

### Remaining implementation tasks

The remaining implementation-owned rows remain unchecked and out of scope, beginning with Stage 1 lifecycle integration. The completed task checkbox was re-read and confirmed as `[x]`.

## Stage 1 task 1.3.1 — Spotify lifecycle integration

- **Status:** completed; only lifecycle task 1.3.1 was authorized and marked `[x]` in `tasks.md`. Diagnostics, documentation, schema/configuration, adapter/registry, OAuth/network/credentials, and Stage 2 remain untouched.
- **Files changed:** `jarvis/src/jarvis/orchestrator/contracts.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/tests/unit/test_loop.py`, and the selected checkbox in `tasks.md`.
- **Behavior:** Added volatile `OperationContext`, replacement cancellation on verified wake, propagation of the loop token to the existing Spotify adapter seam, off/readiness precedence, and post-dispatch epoch/token/switch validation that suppresses late Spotify success before history or speech. Existing conversation, confirmation, TTS/microphone, and non-Spotify paths remain covered by the full suite.
- **Workload:** 141 authored lines across the selected lifecycle source/test/task slice, below the requested 350-line limit. Pre-existing `.atl` working-tree changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added lifecycle tests first; focused execution reported two failures: Spotify dispatch had no operation propagation and a new wake did not replace the previous operation. The readiness test passed against the existing barrier. |
| GREEN | Added `OperationContext`, wake epoch replacement, Spotify operation binding, and stale-result rejection; focused lifecycle tests passed: `3 passed`. |
| TRIANGULATE | Required command passed offline: `1049 passed, 1 warning`; the fake adapter flips the switch before returning success, proving no late Spotify speech/history path, and tests cover epoch replacement plus capture refusal while speaking. The warning is the existing unknown `e2e` mark. |
| REFACTOR | Kept the lifecycle logic in the two authorized orchestrator files, reused existing switch/readiness seams, and avoided changes to the Spotify service, registry, diagnostics, configuration, and unrelated executor behavior. |

### Remaining implementation tasks

The exact unchecked implementation rows remain persisted in `tasks.md`; lifecycle task 1.3.1 is `[x]`, while diagnostics and Stage 1 acceptance remain `[ ]` and were not performed. No Stage 2 task was started.

## Correction work unit `spotify-stage1-interruptible-control-correction`

- **Status:** implementation completed; only the provider-authorized Popen/poll/terminate correction was applied.
- **Scope:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/tests/unit/test_spotify_local.py`, `jarvis/tests/unit/test_loop.py`, and this apply-progress plus verify-report. No other source or test path was changed by this work unit.
- **Behavior:** production playerctl calls now use `Popen` polling with `shell=False`, bounded timeout, prompt terminate/escalating kill, and cancellation-aware result handling. The external off signal cancels the active operation immediately, before the main loop's next tick. Stale Spotify results remain barred from control success, status success, speech, and transcript/history recording.
- **Persisted tasks:** no checkbox changed; the parent lifecycle task remains `[x]`, and this correction addresses its verification blocker. All other task rows remain untouched.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added a Popen cancellation test proving the pre-correction implementation did not terminate a started child, and an external-off signal test proving no immediate token invalidation seam existed; focused tests failed 2 cases. |
| GREEN | Added the cancellable Popen/poll/terminate/kill wait and immediate signal-side token cancellation; focused tests passed: `55 passed`. |
| TRIANGULATE | Required full command passed offline: `1053 passed, 1 warning` (`jarvis/tests/e2e/test_e2e_smoke.py:30`, existing unknown `e2e` mark). Focused fake process evidence confirms cancellation terminates the child and returns `cancelled`; loop evidence confirms external off cancels immediately. No network, credentials, OAuth, hardware, or provider access was used. |
| REFACTOR | Preserved injected callable runners for deterministic tests, retained fixed argv and redacted typed outcomes, and kept cancellation/history/speech gates in the existing lifecycle seams. |

## Files changed by this work unit

- `jarvis/src/jarvis/services/spotify.py`
- `jarvis/src/jarvis/orchestrator/loop.py`
- `jarvis/tests/unit/test_spotify_local.py`
- `jarvis/tests/unit/test_loop.py`
- `openspec/changes/jarvis-spotify-control/apply-progress.md`
- `openspec/changes/jarvis-spotify-control/verify-report.md`

## Remaining tasks and workload boundary

No additional task was authorized. Existing diagnostics/acceptance and Stage 2 rows remain unchecked and outside this correction. Next phase is `sdd-verify`; verification must assess the prior critical blocker.

## Structured status consumed/produced

- **Consumed:** change `jarvis-spotify-control`; artifact store `openspec`; authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; `actionContext.mode: repo-local`; runtime attempt HEAD `sha256:a0b5e131c9de21cac738004dc6aa45bb7cb3ea9fb2bfe1d28416e3818223b24d`.
- **Produced:** apply completed for the authorized correction; `next_recommended: sdd-verify`; no unsafe action-context warnings.


## Prior correction work unit `spotify-stage1-lifecycle-blocked-probe-cancellation-correction`

- **Status:** completed as an authorized correction to the verified critical race; no task checkbox changed.
- **Scope:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/tests/unit/test_spotify_local.py`, and `jarvis/tests/unit/test_loop.py`, plus this apply-progress and the verify report only. Existing unrelated working-tree changes were preserved.
- **Behavior:** Spotify waits execute in a daemon worker while the loop-owned token is polled, so cancellation returns before a blocked probe can advance to control. Spotify transcripts are recorded only after current-operation validation, preventing cancelled control from producing history or spoken success. Fixed argv, `shell=False`, timeout, exact identity, fail-closed errors, generic isolation, and `open_app` remain unchanged.
- **Workload:** 101 correction-authored source/test lines; total relevant working-tree diff remains below the 350-line limit.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added deterministic blocked-probe and blocked-control race tests; the probe test initially remained blocked, and the loop test exposed pre-dispatch Spotify history recording. |
| GREEN | Added interruptible token polling and deferred Spotify transcript recording until post-return validity; focused tests passed: `53 passed`. |
| TRIANGULATE | Required command passed: `1051 passed, 1 warning` with no network, credentials, OAuth, hardware, or provider access. Fake traces prove cancellation produces no control side effect, speech, or history. |
| REFACTOR | Kept the change limited to the existing Spotify wait seam and lifecycle recording boundary; preserved all safety contracts and unrelated behavior.

## Stage 1 task 1.3.2 — safe Spotify diagnostics and documentation

- **Status:** completed; only task 1.3.2 was authorized and marked `[x]` in `tasks.md`.
- **Scope:** Added normalized, fail-closed local capability diagnostics with opt-in host probing, deterministic fake coverage, and credential-free Stage 1 command/boundary documentation. No adapter, service, lifecycle, configuration, OAuth, or provider surface was changed.
- **Files changed:** `jarvis/src/jarvis/diagnose.py`, `jarvis/tests/test_diagnose.py`, `jarvis/docs/comandos_jarvis.md`, and the selected checkbox in `tasks.md`.
- **Behavior:** Diagnostics report only `disabled`, `not_probed`, `missing`, `ambiguous`, or `available`; raw stdout/stderr, executable paths, argv, and secrets are never rendered. Missing or ambiguous identity fails closed. Existing `run_all` and `open_app` behavior remain unchanged.
- **Workload:** 112 authored changed lines across the selected diagnostic, test, documentation, and task surfaces; below the 350-line work-unit limit.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added deterministic tests for disabled, missing, ambiguous, available, redaction, and opt-in behavior; focused tests failed with six missing-function errors. |
| GREEN | Implemented the smallest normalized diagnostic seam; focused tests passed: `23 passed`. |
| TRIANGULATE | Required offline command passed: `1059 passed, 1 warning`; no network, credentials, OAuth, or host probe was used. The warning is the existing unknown `e2e` mark. |
| REFACTOR | Kept probing explicit, fixed the list operation, exposed only safe status/message fields, and preserved existing diagnostic checks and `open_app` semantics. |

## Remaining tasks

The Stage 1 acceptance task and all later Stage 2 implementation rows remain unchecked and outside this authorized work unit.

## Structured status consumed/produced

## Stage 1 task 1.3.3 — offline acceptance

- **Status:** completed; only task 1.3.3 was authorized and marked `[x]` in `tasks.md`.
- **Scope:** acceptance/evidence only. No production, source, test, config, dependency, credential, OAuth, or network changes. Only `tasks.md`, this file, and `verify-report.md` were updated.
- **Required command:** `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q` (Spotify environment variables explicitly unset); result `1059 passed, 1 warning in 50.96s`. Warning is the existing unknown `e2e` mark at `jarvis/tests/e2e/test_e2e_smoke.py:30`.
- **Offline evidence:** deterministic tests use fake runners/adapters and fake lifecycle components; no Spotify credentials were present or used, and no play/pause command was invoked.
- **Read-only Linux probe:** `playerctl --version` → `v2.4.1`; `playerctl -l` → `spotify`; status → `Paused`; metadata → `spotify|Airbag|Pensamientos`. User-bus MPRIS identities were `org.mpris.MediaPlayer2.playerctld` and `org.mpris.MediaPlayer2.spotify`; exactly one Spotify identity. No control action or Spotify launch occurred.
- **Safeguard review:** evidence confirms unchanged allowlisted `open_app`, dedicated Spotify dispatch separate from generic `execute`, cancellation/off/stale suppression, readiness while speaking, TTS/microphone barriers, and history recording only after current-operation validation.
- **TDD Cycle Evidence:** RED was the recorded pre-implementation offline/no-credentials baseline and prior focused failures; GREEN is the passing full offline suite; TRIANGULATE is the deterministic suite plus read-only playerctl/MPRIS probe and safeguard inspection; REFACTOR is review of the independently rollbackable Stage 1 slice with no source edits.
- **Rollback boundary:** unregister `spotify_play`/`spotify_pause` intents and Spotify service/registry handlers; retain existing `open_app spotify`. Do not alter generic `execute`.
- **Remaining:** Stage 2 implementation-owned tasks remain unchecked and are not part of this acceptance task.

- **Consumed:** change `jarvis-spotify-control`; artifact store `openspec`; authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; repo-local action context; parent-authorized work unit `spotify-stage1-safe-diagnostics-docs`.
- **Produced:** apply progress for task 1.3.2; next recommended phase is `sdd-verify`; no unsafe action-context warnings. |

## Authorized safe slice `spotify-stage2-pkce-keyring-boundary`

- **Status:** completed for the bounded replan only. The broad Stage 2 OAuth task remains unchecked; a dedicated checked sub-row was added to `tasks.md`.
- **Scope:** disabled-by-default configuration, fixed approved scopes, pure volatile PKCE transaction model, and keyring-only credential abstraction. No token exchange/refresh, browser/callback listener, API/network, catalog/playback, intents/registry/lifecycle/docs/diagnostics/dependencies, or client ID hardcode/logging.
- **Files changed:** `jarvis/src/jarvis/config.py`, `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_config.py`, `jarvis/tests/unit/test_spotify_oauth.py`, `openspec/changes/jarvis-spotify-control/tasks.md`, and this file.
- **Behavior:** OAuth config defaults disabled and requires explicit enablement plus a validated environment client ID; scopes are exactly `user-read-playback-state` and `user-modify-playback-state`. PKCE generates verifier/state, computes S256, binds transactions to a session, expires them within a bounded TTL, and permits one-time consumption. `KeyringCredentialStore` exposes load/save/delete and returns `storage_unavailable` on absent/broken keyring without file or plaintext fallback.
- **Workload:** 283 authored added lines and 1 deletion including the new focused test file, below the user-specified 350-line limit. Existing unrelated working-tree changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added focused config/OAuth tests before implementation; collection failed because the new OAuth exports/config seam did not exist. |
| GREEN | Added the minimal config, PKCE model, and keyring boundary; focused tests passed: `18 passed`. |
| TRIANGULATE | Full required command reached `1067 passed, 1 failed, 1 warning`; the sole failure is unrelated existing proactive usage-note state in `jarvis/tests/test_imports.py::test_cli_start_runs_real_pipeline`, which observed `firefox 121 veces`. `git diff --check` and `py_compile` passed. No network, credentials, token exchange, callback, or API call was used. |
| REFACTOR | Kept OAuth code isolated in existing Spotify/config seams, hid verifier/state/value from repr, bounded validation, and left the broad OAuth task and all excluded surfaces untouched. |

## Remaining tasks

The broad Stage 2 OAuth task and all other Stage 2 implementation rows remain unchecked. The exact broad OAuth row remains `[ ]`; the checked sub-row is intentionally not a completion of that broad task.

## Structured status consumed/produced

- **Consumed:** change `jarvis-spotify-control`; artifact store `openspec`; authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; repo-local action context with allowed edit root `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; strict TDD active; user resolved high-risk delivery as bounded safe slice with a 350-line cap.
- **Produced:** `next_recommended: sdd-verify` for this slice; apply remains incomplete for the overall change because broad Stage 2 tasks are unchecked. No action-context warnings.

## Authorized work unit `spotify-stage2-injected-token-lifecycle`

- **Status:** completed for the injected offline token-lifecycle slice. The broad Stage 2 OAuth task remains unchecked; the dedicated safe-slice row is checked in `tasks.md`.
- **Scope:** added injected, bounded PKCE code exchange; fixed approved scopes; keyring-only token persistence; expiry-aware one-flight refresh with refresh-token rotation; local revoke/disable cleanup; invalid-grant and API 401 cleanup; and typed redacted errors. No browser, callback listener, live transport, catalog, playback, intents, documentation, or provider calls were added.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_oauth.py`, `openspec/changes/jarvis-spotify-control/tasks.md`, and this file.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added five focused lifecycle tests first; the suite initially failed at collection because `OAuthClient` and typed lifecycle results were absent. |
| GREEN | Implemented the smallest injected transport client with PKCE exchange, expiry refresh, rotation, cleanup, and safe result mapping; focused tests passed: `23 passed`. |
| TRIANGULATE | Focused OAuth/config tests passed: `23 passed`; the required full suite reached `1072 passed, 1 failed, 1 warning`, with the unrelated existing proactive usage-note assertion in `jarvis/tests/test_imports.py::test_cli_start_runs_real_pipeline` failing because live usage reported `firefox 124 veces`. No network, credentials, callback, or live transport was used. |
| REFACTOR | Added a descriptive client alias, retained keyring-only storage, hid token material from result representations, and kept all behavior in the authorized Spotify service/test surfaces. |

## Remaining tasks and workload boundary

The broad OAuth row and all catalog, playback, lifecycle, diagnostics, documentation, and release rows remain unchecked and outside this work unit. The implementation slice is 350-line bounded and parent-authorized under `auto-chain`; no commit or push was performed by this executor.

## Structured status consumed/produced

- **Consumed:** change `jarvis-spotify-control`; artifact store `openspec`; authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; `actionContext.mode: repo-local`; allowed edit root is that workspace; parent-authorized work unit `spotify-stage2-injected-token-lifecycle`; strict TDD active; delivery resolved as `auto-chain`; parent attempt authority `523bd3c7146b151b2886e28b1ca654bf9efa32d063a3c26fb2ab8a162f975061`.
- **Produced:** apply progress for the checked dedicated slice; `next_recommended: sdd-verify`; no unsafe action-context warnings.

## Authorized correction `spotify-oauth-disable-expiry-fail-closed`

- **Status:** completed; bounded to the durable OAuth disable marker and fail-closed expiry parsing correction.
- **Scope:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_oauth.py`, and this progress artifact only. No external calls, credentials, network, task checkbox, or unrelated source/test surface was changed.
- **Behavior:** `disable()` persists a separate keyring marker and removes token material; marker state blocks access until a successful authorized save clears it. OAuth expiry values now require a non-boolean, finite, strictly positive numeric value, and persisted expiry records receive the same validation.
- **Workload:** 113 source/test authored changed lines (111 net), within the user-authorized 120-line correction limit; progress documentation is additional OpenSpec evidence and is not part of the source/test correction budget.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added expiry parametrization and durable-disable regression tests first; focused OAuth tests failed for NaN/infinity/nonpositive/boolean expiry and missing disabled-state handling. |
| GREEN | Added keyring marker status, separate disable path, disabled-load handling, and finite-positive expiry validation; focused suite passed: `20 passed`. |
| TRIANGULATE | Required full command passed `1080 passed, 1 failed, 1 warning`; the sole failure is the pre-existing live proactive usage-note assertion in `jarvis/tests/test_imports.py::test_cli_start_runs_real_pipeline` (`firefox 127 veces`). `git diff --check` passed. No network, credentials, OAuth provider, or external call was used. |
| REFACTOR | Kept revoke deletion semantics separate from durable disable, preserved keyring-only storage, and limited edits to the authorized Spotify OAuth source/test seams. |

### Remaining tasks and status

No persisted task checkbox was changed: this was a correction to the existing OAuth lifecycle slice, while the broad OAuth task and all other implementation rows remain as previously recorded. `actionContext.mode` was repo-local with the authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; no warnings or unsafe edit-root conditions were present. Next recommended phase is `sdd-verify`.

## Follow-up correction `spotify-oauth-disable-exchange-and-scope-validation`

- **Status:** implementation completed; this follow-up stayed within the existing OAuth correction boundary and remains uncommitted.
- **Scope:** `jarvis/src/jarvis/services/spotify.py` and `jarvis/tests/unit/test_spotify_oauth.py`. No task checkbox, credential, network, provider, or unrelated source surface was changed.
- **Behavior:** Durable disabled state now blocks `exchange_code()` before transport even if credentials are restored; explicit `enable()` is the only reactivation path. Persisted scope records accept only string collections with exactly the approved scopes and return typed `INVALID_RESPONSE` after cleanup for malformed shapes, without raising.
- **Verification:** focused OAuth tests `26 passed`; full suite `1088 passed, 1 warning`; `git diff --check` passed. The remaining warning is the pre-existing unknown `e2e` pytest marker at `jarvis/tests/e2e/test_e2e_smoke.py:30`.
- **Boundary:** no commit or push was performed. The broad OAuth task and remaining Stage 2 rows remain unchecked and require separate authorized work units.

## Authorized work unit `spotify-stage2-loopback-callback-state`

- **Status:** completed for the provider-authorized offline callback safe slice. The broad OAuth task remains unchecked; only the dedicated callback sub-row was marked `[x]` in `tasks.md`.
- **Scope:** `parse_pkce_callback()` validates injected callback URLs against the exact `http://127.0.0.1:8888/callback` shape, requires exactly one non-empty `code` and `state`, binds the transaction to the session, enforces expiry and one-time consumption, and compares state with `hmac.compare_digest`. The existing PKCE transaction model is reused. No listener, browser, network, token exchange invocation, catalog, playback, client ID, config, intent, registry, lifecycle, or documentation behavior was added.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_oauth.py`, and the dedicated safe-slice checkbox in `openspec/changes/jarvis-spotify-control/tasks.md`. `apply-progress.md` records this evidence.
- **Workload:** 105 net changed lines in the allowed source/test/task surfaces before this evidence entry (50 additions/1 deletion in source, 54 test additions, 1 task line); within the provider-enforced 120-line bound. No client ID was added to the tests or implementation.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added four focused callback tests before implementation; collection failed because `OAuthCallbackCode` and `parse_pkce_callback` were absent. |
| GREEN | Added the pure parser and exact redirect constant; focused OAuth suite passed: `30 passed`. |
| TRIANGULATE | Required full command passed: `1089 passed, 3 deselected` in 35.31s. `git diff --check` and `jarvis/.venv/bin/python -m compileall -q jarvis/src` passed. Tests used injected strings, transactions, and clocks only; no browser, socket, network, credentials, client ID, token exchange, or provider was used. |
| REFACTOR | Kept callback handling as a small offline seam beside the existing PKCE model, used typed safe outcomes with hidden authorization code representation, reused the canonical redirect constant, and preserved all excluded surfaces. |

### Structured status consumed/produced

- **Consumed:** change `jarvis-spotify-control`; artifact store `openspec`; authoritative workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; `actionContext.mode: repo-local`; allowed edit roots limited to the canonical workspace; strict TDD active; provider-authorized work unit `spotify-stage2-loopback-callback-state`; parent runtime token authenticated without a second attempt.
- **Produced:** apply progress for the dedicated callback safe slice; next recommended phase `sdd-verify`; broad OAuth and all catalog/playback/release rows remain unchecked. No commit or push was performed.

## Authorized work unit `spotify-stage2-catalog-clarification`

- **Status:** completed for the provider-authorized offline/injected catalog safe slice. The broad catalog task remains unchecked; only the dedicated safe-slice row was marked `[x]` in `tasks.md`.
- **Scope:** Added `CatalogClient`, bounded album/artist search request construction for the official `/v1/search` endpoint, safe no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, one-time resolution, replacement/TTL/off/cancellation invalidation, and a provider-injection-only boundary. No live HTTP, token exchange, browser, socket, playback, intents, registry, lifecycle, diagnostics, documentation, or generic execution behavior was added.
- **Files changed by this work unit:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_catalog.py`, `openspec/changes/jarvis-spotify-control/tasks.md`, and this progress artifact. Pre-existing unrelated `.atl` changes were preserved.
- **Workload:** 151 added source lines, 149 added test lines, and 1 task checkbox line in this bounded slice; no commit or push was performed. The prior broad feature forecast remains high-risk and is not authorized by this slice.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added `jarvis/tests/unit/test_spotify_catalog.py` first; collection failed because `CatalogCode`/`CatalogClient` were absent. The tests cover bounded endpoint parameters, supported kinds, empty/single/multiple results, opaque IDs, session/TTL/one-time selection, replacement, off, cancellation, malformed payload items, and the no-playback contract. |
| GREEN | Implemented the smallest injected-only catalog boundary and corrected one test assertion to inspect the normalized resolved candidate; focused catalog tests passed: `8 passed`. |
| TRIANGULATE | Focused Spotify regression set passed: `65 passed`; required full offline suite passed: `1097 passed, 3 deselected`; `jarvis/.venv/bin/python -m compileall -q jarvis/src` and `git diff --check` passed. All provider interactions were fake-callable injections; no network, sockets, secrets, token exchange, browser, playback, or live provider was used. |
| REFACTOR | Kept raw provider payloads out of `CatalogCandidate`, bounded the official endpoint contract, centralized pending-selection invalidation, and left broad OAuth, playback, intent, registry, lifecycle, diagnostics, documentation, and generic execution rows untouched. |

### Remaining tasks

The broad catalog row remains intentionally unchecked, along with the following unrelated Stage 2 rows; the persisted `tasks.md` artifact is authoritative:

- [ ] Add authorized album/artist catalog contracts and normalization at `jarvis/src/jarvis/services/spotify.py` (split catalog client if necessary) with tests in `jarvis/tests/unit/test_spotify_catalog.py`: bounded query/results, official search endpoint only, no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, replacement/TTL/off/cancellation invalidation, and no playback during search or ambiguity. <!-- sdd-owner: implementation -->
- [ ] Extend validated intent prompts/patterns and dispatch for `spotify_search` and `spotify_play_selection` in `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/interpreter/golden.py`, and `jarvis/src/jarvis/actions/base.py`; add tests in `jarvis/tests/unit/test_spotify_intents.py` proving numbers/exact pending references are the only clarification selectors and arbitrary URI/device/entity data cannot cross the boundary. <!-- sdd-owner: implementation -->
- [ ] Implement Premium/account/device readiness and playback policy in `jarvis/src/jarvis/services/spotify.py` with tests in `jarvis/tests/unit/test_spotify_playback.py`. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 2 status/error speech, diagnostics, history/log redaction, and lifecycle cancellation in the existing action/orchestrator/diagnostics/log surfaces. <!-- sdd-owner: implementation -->
- [ ] Document OAuth consent, minimum scopes, Premium requirement, local-only versus networked behavior, clarification rules, target restrictions, disable/revoke procedure, and rollback. <!-- sdd-owner: implementation -->
- [ ] Run the complete required pytest command and an explicitly authorized, bounded integration smoke test only if credentials, keyring, network, Premium account, Spotify Desktop, and the configured target are all available. <!-- sdd-owner: implementation -->

### Structured status consumed/produced

- **Consumed:** provider-authorized work unit `spotify-stage2-catalog-clarification`; runtime attempt token `sha256:616cb9bcd4674c2c12a22c41f851a6edfddc371c91048b412f838c7cdee90cd4`; canonical repo `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; repo-local action context with edits limited to the four user-specified surfaces; strict TDD active; high-risk forecast resolved by this bounded safe slice.
- **Produced:** apply progress for the dedicated catalog safe slice; `next_recommended: sdd-verify`; broad catalog, OAuth, playback, intents, lifecycle, diagnostics, documentation, and release rows remain unchecked. No commit or push was performed.

## Authorized work unit `spotify-stage2-search-selection-intents`

- **Status:** completed for task 2.2.2 only; the broad catalog task and all other Stage 2 rows remain unchecked.
- **Scope:** Added validated `spotify_search` and `spotify_play_selection` schema entities, deterministic Spanish golden forms, compact classifier prompt allowlisting, and optional dedicated dispatch to the existing injected catalog boundary. Numeric and opaque pending selectors are bounded; URI, device, provider, backend, playlist, recommendation, and generic execution fields are rejected.
- **Files changed:** `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/golden.py`, `jarvis/src/jarvis/actions/base.py`, `jarvis/tests/unit/test_spotify_intents.py`, and the selected checkbox in `tasks.md`. `interpreter.py` was inspected and remained unchanged because its validated LLM path already accepts the schema boundary.
- **Non-goals preserved:** No `service.py` edits, network, secrets, browser, sockets, token exchange, playback, lifecycle, diagnostics, documentation, or generic execution behavior.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | New focused tests failed 7 cases: search forms routed to `web_search`, selectors were unmatched, and the dedicated intent behavior was absent. |
| GREEN | Added schema constraints, Spanish search/selection golden patterns, prompt allowlisting, and injected catalog dispatch; focused suite passed `15 passed`. |
| TRIANGULATE | Focused interpreter/schema/golden/registry/catalog/service suite passed `345 passed`; full required `jarvis/.venv/bin/pytest -q` passed `1112 passed, 3 deselected`; compileall and `git diff --check` passed. |
| REFACTOR | Kept Stage 2 dispatch optional and separate from existing local Spotify handlers, returned only safe candidate metadata, preserved generic `execute`, callback/PKCE/catalog boundaries, and made no service edits. |

### Verification and workload

- Changed implementation/test scope: 116 source diff lines plus 133 lines in the new focused test file; OpenSpec evidence is additional. Unrelated pre-existing `.atl` changes were preserved.
- Persisted task row 2.2.2 was re-read and confirmed `[x]`; no other task checkbox was changed.
- Structured status consumed: change `jarvis-spotify-control`, `applyState: ready`, repo-local canonical workspace, strict TDD active, allowed files limited by parent, and parent token `sha256:e0ec4befd655344a3737cdce6f98b58875f31aadf47a2d434519e92ec5b11914`.
- Structured status produced: apply complete for this work unit; `next_recommended: sdd-verify`; no commit or push performed.

## Authorized work unit `spotify-stage2-playback-policy`

- **Status:** completed for task 2.3.1 only; all other unchecked implementation rows remain untouched.
- **Scope:** Added an injected-only `PlaybackPolicy` with `PlaybackOperation`, typed playback outcomes, exact approved-scope and Premium checks, unique local Spotify identity validation, exactly one configured computer fingerprint, pending-catalog selection resolution, bounded API calls, readback verification, cancellation checks, and fail-closed target/content handling. No transfer, device switching, Connect/MPRIS/browser fallback, sockets, secrets, network transport, or live provider behavior was added.
- **Files changed:** `jarvis/src/jarvis/services/spotify.py`, `jarvis/tests/unit/test_spotify_playback.py`, and the task 2.3.1 checkbox in `tasks.md`. Pre-existing `.atl` changes were preserved.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | Added `test_spotify_playback.py` first; collection failed because the new playback policy exports were absent. |
| GREEN | Implemented the smallest injected policy; focused playback suite passed: `10 passed`. |
| TRIANGULATE | Fake API/local-identity tests cover approved scopes, Premium, missing/ambiguous desktop targets, unknown selections, URI restrictions, bounded calls, readback uncertainty, cancellation, and absence of fallback endpoints. Full pytest, compileall, and diff checks are recorded below. |
| REFACTOR | Kept playback behind `play_selection`, made direct provider/transport injection mandatory, restricted context URIs to current catalog candidates, and retained existing OAuth, PKCE, catalog, intents, and Stage 1 behavior. |

### Verification and workload

- Required focused command: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_playback.py` → `10 passed`.
- Full command: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q`.
- Compile command: `jarvis/.venv/bin/python -m compileall -q jarvis/src`.
- `git diff --check` passed before final verification.
- Authenticated provider runtime token: `sha256:7ebbf6e9f706c05dfbd9883148db150f11770187b8ebc5225d700de7eb856c00`.
- Workload boundary: 163 added source lines and 155 added focused-test lines; task/progress evidence is outside the implementation count. No commit or push performed.
- Structured status consumed: change `jarvis-spotify-control`, repo-local canonical workspace, strict TDD active, allowed edit surfaces exactly as user specified, and provider-authorized bounded work unit `spotify-stage2-playback-policy`. `next_recommended: sdd-verify`.

## Authorized work unit `spotify-stage2-status-error-lifecycle`

- **Status:** completed as a project-local exception. Native SDD apply was blocked by stale intended-untracked metadata for a playback test that is already tracked; the parent explicitly authorized this bounded implementation and evidence update.
- **Scope:** added injected Stage 2 catalog/playback dispatch with typed safe speech, opt-in normalized Stage 2 diagnostics, OAuth redaction for transcript/history surfaces, and operation-context propagation for catalog/playback handlers. No Spotify provider source, OAuth transport, playback policy, config, dependency, browser, socket, or network behavior was changed.
- **Files changed:** `jarvis/src/jarvis/actions/base.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/diagnose.py`, `jarvis/src/jarvis/orchestrator/logs.py`, and focused regression tests in the corresponding allowed test surfaces.
- **TDD evidence:** RED focused tests failed for the absent Stage 2 dispatch, diagnostics, and redaction seams; GREEN focused tests passed after minimal implementation; TRIANGULATE covered typed Premium/clarification mapping and secret removal; REFACTOR retained fail-closed defaults and injected-only behavior.
- **Safety:** no raw provider output, tokens, authorization codes, state, verifier, URI, device ID, or arbitrary command data is spoken or persisted. Cancellation remains checked before late speech/history and operation context reaches injected Stage 2 handlers.
- **Verification:** focused slice `93 passed`; full suite, compileall, and diff check are recorded in the handoff. No commit or push performed.

## Current documentation/reconciliation slice

## Authorized safe slice `spotify-search-and-play-same-process`

- **Status:** completed for the bounded offline/injected CLI flow; broad Stage 2 rows remain unchanged.
- **Behavior:** `spotify search-and-play --kind album|artist --query TEXT [--limit N]` searches through the OAuth/catalog bridge, prints only safe numbered metadata, requires an explicit numeric selection even for one result, resolves the same volatile catalog session, then invokes `PlaybackPolicy`. EOF, Ctrl-C, invalid numbers, unavailable OAuth, Premium, identity, fingerprint, device, or readback gates fail closed before playback.
- **Files:** `jarvis/src/jarvis/cli.py`, `jarvis/src/jarvis/config.py`, `jarvis/src/jarvis/services/spotify.py`, and focused tests. No cross-process persistence, browser, keyring mutation, live provider, or playback was used.

### TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | New config, OAuth adapter, and CLI selection tests failed because the target config, playback adapter, and command flow were absent. |
| GREEN | Added the minimal same-process flow and fixed official-endpoint OAuth adapter; focused tests passed: `150 passed`. |
| TRIANGULATE | Full suite passed `1273 passed, 3 deselected`; tests cover EOF, explicit selection, safe output, OAuth/catalog/playback gates, and readback. |
| REFACTOR | Kept selection volatile and in-memory, restricted adapter endpoints, preserved standalone search and Stage 1, and did not run live capabilities. |

- **Status:** completed as an explicitly authorized project-local reconciliation.
  Historical entries above are preserved. Only the documentation, progress,
  verification, and task surfaces named by the parent were edited.
- **Task reconciliation at this checkpoint:** checked only the completed 2.3.2
  lifecycle/redaction row and the 2.4 documentation row in `tasks.md`. The
  separate 2.4 release-verification row was still pending at that historical
  checkpoint; the later reconciliation below records its conditional offline
  completion. Broad OAuth/catalog rows remain unchecked.
- **Documentation:** `jarvis/docs/comandos_jarvis.md` now states Stage 2's
  explicit opt-in, exact two scopes, Premium requirement, Stage 1 offline vs
  Stage 2 network boundary, mandatory multiple-result clarification, exact
  **Spotify Desktop en esta PC** target, disable/revoke, fail-closed behavior,
  rollback preserving Stage 1, and privacy/no-secrets rules. It does not promise
  fallback, device switching, browser automation, or automatic selection.
- **Project-local exception:** native SDD reconciliation was necessary because
  stale intended-untracked metadata names a playback test that is already
  tracked. This exception is documented, but no native SDD verification is
  claimed. No live Spotify verification, provider call, credentials, or network
  smoke test was performed.

### Documentation/privacy TDD evidence

| Cycle | Evidence |
|---|---|
| RED | Review identified missing explicit gates, boundaries, clarification, target, rollback, and secret-handling guidance. |
| GREEN | Added concise Spanish guidance while preserving independently usable Stage 1 instructions. |
| TRIANGULATE | Cross-checked wording against the design and ran existing injected redaction, diagnostics, lifecycle, intent, OAuth, and playback tests; no live/native SDD verification. |
| REFACTOR | Kept the change additive and bounded; removed ambiguity around fallback, device selection, browser automation, and automatic result choice. |

### Validation

- `cd /home/ale/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/test_diagnose.py jarvis/tests/unit/test_spotify_intents.py jarvis/tests/unit/test_spotify_playback.py jarvis/tests/unit/test_spotify_oauth.py jarvis/tests/unit/test_actions_base.py jarvis/tests/unit/test_loop.py` → `139 passed in 19.58s`.
- `cd /home/ale/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q` → `1127 passed, 3 deselected in 33.31s`.
- `cd /home/ale/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src` → exit 0, no output.
- `cd /home/ale/Proyectos/jarvis-dev && git diff --check` → exit 0, no output.
- No live Spotify, native SDD, credentials, or network verification was performed; no commit or push was performed.

## 2.4 release-verification reconciliation

- **Status:** conditionally complete for offline release readiness; the overall change remains incomplete because broad OAuth/catalog implementation rows remain unchecked.
- **RED:** the pre-release matrix identified live smoke prerequisites that were not exercised: credentials, keyring, network, Premium account, Spotify Desktop, and the configured target. Live smoke was therefore deferred; no native SDD verification or live provider action occurred.
- **GREEN:** the full offline suite passed (`1127 passed, 3 deselected`); focused Stage 2 verification passed (`167 passed`); `jarvis/.venv/bin/python -m compileall -q jarvis/src` passed; and `git diff --check` passed.
- **TRIANGULATE:** rollback was verified with fake keyring/stores, including disable/revoke cleanup without plaintext fallback. Stage 1 behavior and the allowlisted `open_app` path were preserved. Tracked-artifact review found no secrets or raw catalog data.
- **REFACTOR:** evidence was reconciled into this bounded conditional release-readiness record without changing source, tests, docs, config, dependencies, `.atl`, or historical entries. The stale native SDD ledger exception is preserved: intended-untracked metadata names a playback test that is already tracked, so no native SDD verification is claimed.
- **Limitations:** this is conditional offline readiness, not live integration acceptance. No credentials, keyring, network, Premium/Desktop target, native SDD verifier, or provider action was exercised. No commit or push was performed.

## 2026-09-11 session checkpoint

- **Delivered:** Client ID keyring persistence/setup (`67fe681`), idempotent Secret Service setup fix (`55432b6`), configured local Spotify play/pause wiring and natural aliases (`22635a5`), and prior lifecycle/redaction/docs/release evidence (`eb38937`, `4809714`, `2d55365`).
- **Verification:** latest control slice passed focused `139` and full `1156` tests with `3` E2E deselected; compileall and diff check passed. Keyring dependency is installed in the project venv; the configured Client ID is stored only in the system keyring.
- **Known limitation:** album search/API wiring and the full OAuth browser/callback integration remain unfinished. Live smoke was not run. Native SDD attempt metadata remains stale and is intentionally not edited; `.atl` changes remain excluded.
- **Resume next session:** implement the smallest injected OAuth/catalog integration slice, then wire a non-voice authorization/test entrypoint before any live smoke. Keep Stage 1 Desktop playback and Stage 2 fail-closed boundaries intact.

## Authorized offline OAuth-to-catalog bridge slice

- **Status:** completed as a bounded injected-only bridge; broad OAuth/catalog rows remain unchecked.
- **Scope:** `SpotifyCatalogBridge` obtains a token through the existing `OAuthClient` seam, delegates normalization to `CatalogClient`, and permits only bounded GET `/v1/search` album/artist requests through an injected transport with Bearer header and timeout. Typed safe outcomes cover disabled, unauthorized, storage unavailable, timeout, API 401, and provider failure. No browser, socket, live network, playback, token/payload logging, or provider details were added.
- **TDD:** RED focused bridge tests failed at collection because the bridge exports were absent. GREEN added the minimal adapter; OAuth/catalog tests passed (`56 passed`). TRIANGULATE covered exact method/endpoint/params/header/timeout, unsupported kinds, no transport on OAuth failures, 401/timeout/provider failures, normalization, and redaction. REFACTOR kept the bridge in the existing Spotify service seam and left Stage 1 controls, `open_app`, intents, registry, lifecycle, voice, and playback behavior unchanged.
- **Limitations:** offline/injected evidence only; no live provider or browser smoke test. No broad OAuth/catalog task checkbox was marked complete. No commit or push was performed.


## Authorized safe slice `spotify-oauth-cli-entrypoint`

- **Status:** completed for this bounded code-only entrypoint; the broad OAuth task remains unchecked.
- **Scope:** `jarvis spotify authorize` constructs a gated PKCE authorization URL without opening a browser; state and code-challenge are redacted in CLI output. `authorize_spotify_callback()` is an injected parser/exchange seam reusing `PKCETransaction`, `parse_pkce_callback`, `OAuthClient`, `KeyringCredentialStore`, and `LOOPBACK_REDIRECT_URI`.
- **Safety:** no browser, socket/listener, network/provider call, or keyring mutation is performed by the CLI or tests. Disabled/missing gate, invalid callback/state/session, expiry, storage, timeout, and provider failures remain fail-closed through existing typed seams. Existing setup Spotify alias and generic CLI paths remain unchanged.
- **TDD evidence:** RED focused tests failed at missing entrypoint exports/routing; GREEN focused CLI/OAuth tests passed (`46 passed`); TRIANGULATE covered exact redirect/scopes, URL redaction, invalid callback no-transport, and injected success; REFACTOR retained the existing OAuth and callback boundaries with no live execution path.
- **Validation:** focused CLI/OAuth tests passed; compileall and `git diff --check` were run. No overall OAuth completion is claimed; live authorization requires a separate explicit authorization decision.

## Authorized code-only live OAuth slice `spotify-oauth-live-loopback`

- **Status:** implemented as a bounded explicit `spotify authorize --live` mode; the broad OAuth task remains unchecked.
- **Scope:** injected browser opener, fixed `127.0.0.1:8888` one-request callback server, parser/state/expiry validation, injected token exchange, and existing keyring-only storage. Bind failure, invalid/declined/expired callbacks, timeout, provider/401, and storage failures return safe typed statuses. No live mode was executed.
- **Safety:** no arbitrary host or fallback port; no token, code, verifier, state, or payload output/logging. Browser, server, transport, clock, transaction, and store seams are deterministic in tests. Existing generic CLI, setup, Stage 1 controls, catalog bridge, and playback remain unchanged.
- **TDD evidence:** RED: two focused tests failed at the absent live export. GREEN: focused OAuth/CLI tests passed (`50 passed`). TRIANGULATE: invalid/declined callbacks and bind failure make no transport/browser fallback; compileall and diff check passed. REFACTOR: production defaults remain behind the explicit live mode and shutdown is bounded/finally-owned.
- **Limitation:** this is code-only offline evidence; no browser, socket, network/provider, or real keyring side effect was executed. The broad OAuth task is not marked complete.

## Bootstrap authorization correction

- **Status:** completed as a narrow correction to the live OAuth bootstrap contradiction.
- **Behavior:** authorization URL construction remains authorized by default and permits pending authorization only with `allow_pending_authorization=True`; the live flow uses that flag before callback validation. The OAuth client factory remains authorized by default and permits the initial post-callback exchange only with `allow_initial_exchange=True`.
- **TDD:** RED: focused OAuth/CLI tests reported four failures for missing flags and unauthorized live bootstrap. GREEN: focused OAuth/CLI tests passed (`53 passed`). TRIANGULATE: invalid callback/state remains transport-free and the validated callback exchange succeeds; disabled, missing-client, scope, session, and callback gates remain fail-closed. REFACTOR: flags are keyword-only, explicit, and limited to their respective bootstrap boundaries.
- **Validation:** compileall and `git diff --check` were run after the correction. Live authorization remains unexecuted; no browser, socket, network/provider, or real keyring mutation occurred.

## First-authorization bootstrap correction

- **Status:** completed as a narrow configuration/OAuth safety correction.
- **Behavior:** with `SPOTIFY_API_ENABLED=true`, explicit `SPOTIFY_AUTHORIZED=false`, a valid keyring Client ID, and a bounded TTL, configuration now returns `enabled=True`, `authorized=False`, the Client ID, and the fixed two-scope policy. Missing/invalid Client IDs, disabled or invalid configuration, and invalid TTLs remain disabled defaults. The normal OAuth factory still requires authorization except for its explicit initial-exchange flag.
- **TDD evidence:** RED: the new pending-authorization config test returned disabled defaults. GREEN: the loader now validates the explicit pending state and keyring ID before returning the safe snapshot. TRIANGULATE: focused config/OAuth tests passed (`67 passed`), including disabled/no-keyring probing, invalid keyring values, pending URL/factory gates, and transport-free callback rejection. REFACTOR: keyring access remains limited to explicitly enabled, valid, bounded configuration; no environment Client ID fallback was added.
- **Validation:** `jarvis/.venv/bin/python -m compileall -q jarvis/src/jarvis jarvis/tests/unit/test_config.py jarvis/tests/unit/test_spotify_oauth.py` passed; `git diff --check` passed. No browser, sockets, network/provider call, or real keyring mutation occurred.

## Live callback timeout correction

- **Status:** completed as a narrow bounded correction; the broad OAuth task remains unchecked.
- **Behavior:** the explicit live callback window now defaults to 120 seconds and accepts an optional `--timeout` value, with a hard maximum of 120 seconds and no unbounded wait. The token HTTP transport remains independently capped at 30 seconds. Loopback binding, exact redirect, one callback, state/session/expiry validation, one-time consumption, cleanup, and fail-closed errors are unchanged.
- **TDD evidence:** RED: focused OAuth/CLI tests failed for the missing 120-second window and CLI timeout route (3 failures). GREEN: focused OAuth/CLI tests passed (`57 passed`). TRIANGULATE: 120 seconds reaches the fixed loopback server; 120.1 seconds is rejected before browser/server use; existing invalid/declined/bind-failure and redaction tests remain green. REFACTOR: timeout constants are centralized and the live window is kept separate from the token transport limit.
- **Validation:** no browser, socket, network/provider call, or real keyring mutation was performed.

## Live OAuth CLI diagnostic correction

- **Status:** completed as a narrow diagnostics-only correction; live authorization was not executed.
- **Behavior:** failed `spotify authorize --live` output now includes the existing `OAuthErrorCode.value` alongside the existing safe message. Raw provider payloads, tokens, authorization code, state, verifier, URL, and exceptions remain unprinted.
- **TDD evidence:** RED: the focused CLI test failed because `provider_error` was absent from stderr. GREEN: focused CLI tests passed (`7 passed`). TRIANGULATE: the test injects token and provider-payload sentinels and confirms neither is printed; existing timeout, bounded-timeout, and explicit-live routing tests remain green.
- **Validation:** no live retry, browser, socket, network/provider call, or real keyring mutation was performed.

## OAuth callback diagnostic hardening

- **Status:** completed within the authorized OAuth/CLI surfaces. Callback validation failures preserve `OAuthErrorCode.INVALID_RESPONSE` and now carry the typed `OAuthCallbackCode` category for diagnostics.
- **Behavior:** the live CLI prints only the safe callback category (for example `state_mismatch`, `invalid_path`, `invalid_query_keys`, `duplicate_or_empty_query`, `fragment_present`, `expired`, or `already_consumed`) for callback validation failures. Callback URL, authorization code, state, verifier, token, and provider payload values are not included.
- **TDD evidence:** RED: focused OAuth/CLI tests failed before the structural categories existed. GREEN: focused OAuth/CLI tests passed (`73 passed`). TRIANGULATE: parametrized path/query/duplicate/empty/fragment cases preserve the unconsumed transaction; CLI sentinel tests confirm only the category is printed. REFACTOR: parsing uses bounded query pairs while retaining the exact redirect and state checks.
- **Validation:** `jarvis/.venv/bin/python -m compileall -q jarvis/src` passed; `git diff --check` passed. No live authorization retry, browser open, network/provider call, keyring mutation, commit, or push was performed.

## OAuth invalid-query key summary correction

- **Status:** completed as a bounded diagnostics-only correction.
- **Behavior:** invalid query-key failures now expose only `keys:` followed by at most six names. Only `code`, `state`, `scope`, `error`, `error_description`, and `error_uri` are emitted; every other key is rendered as `unknown`. Query values and callback URLs remain excluded, and callback validation remains fail-closed.
- **TDD evidence:** RED: new OAuth/CLI tests failed because callback results had no sanitized diagnostic field and CLI results had no diagnostic transport. GREEN: focused OAuth/CLI tests passed (`76 passed`). TRIANGULATE: tests cover known-key summaries, attacker-key redaction/bounding, CLI output, and unchanged callback categories. REFACTOR: diagnostics remain separate from typed callback categories and hidden from result representations.
- **Validation:** compileall and `git diff --check` passed. No live authorization retry, browser open, network/provider call, keyring mutation, commit, or push was performed.

## Spotify standard OAuth issuer parameter correction

- **Status:** completed as a bounded offline callback-parser correction.
- **Behavior:** `iss` is accepted as an optional callback parameter only when it equals exactly `https://accounts.spotify.com`; missing, invalid, empty, duplicate, and arbitrary parameters remain fail-closed. Exactly one non-empty `code` and `state`, exact loopback redirect, fragment rejection, session/state binding, expiry, and one-time consumption are preserved.
- **Diagnostics:** `iss` is allowlisted by name only; issuer values, codes, state, URLs, and other secrets remain absent from sanitized diagnostics and CLI output.
- **TDD evidence:** RED: focused OAuth/CLI tests reported four issuer/diagnostic failures. GREEN: focused OAuth/CLI tests passed (`81 passed`). TRIANGULATE: existing structural, state/session, expiry, consumed-transaction, redaction, and CLI tests remain green; compileall and diff checks passed. No live authorization retry, browser, socket, network/provider call, keyring mutation, commit, or push was performed.

## Spotify confirmed `ubi` callback parameter correction

- **Status:** completed as a narrow offline callback-parser and diagnostics correction.
- **Behavior:** `ubi` is accepted once as an optional non-empty callback parameter; its value is ignored and never included in results or diagnostics. The exact `iss` allowlist remains unchanged. Required `code`/`state`, duplicate/empty checks, extra-key rejection, redirect/fragment, state/session, expiry, and one-time-consumption protections remain fail-closed.
- **Diagnostics:** `ubi` is recognized by name only in bounded key summaries; callback values and URLs remain excluded from OAuth and CLI output.
- **TDD evidence:** RED: focused OAuth tests reported four failures before the allowlist/parser update. GREEN: focused OAuth/CLI tests passed (`83 passed`). TRIANGULATE: duplicate/empty `ubi`, combined `iss`/`ubi`, sanitized key diagnostics, and existing callback/CLI safety tests pass. REFACTOR: the optional-key combinations remain explicit and narrowly allowlisted.
- **Validation:** no live authorization retry, browser open, socket, network/provider call, real keyring mutation, commit, or push was performed.

## OAuth token HTTP status diagnostic correction

- **Status:** completed as a bounded offline OAuth/CLI diagnostics correction.
- **Behavior:** token-exchange HTTP failures preserve `OAuthErrorCode.PROVIDER_ERROR` and expose only `token_http_400`, `token_http_401`, or `token_http_other`. The CLI allowlists these categories and never prints provider payloads or OAuth material. `invalid_grant` cleanup and fail-closed credential handling remain unchanged.
- **TDD evidence:** RED: focused OAuth/CLI tests failed in six cases because the typed diagnostic field and CLI category output were absent. GREEN: focused OAuth/CLI tests passed (`89 passed`). TRIANGULATE: parametrized 400/401/other statuses, payload redaction, unchanged provider code, and CLI output allowlisting are covered.
- **Validation:** `jarvis/.venv/bin/python -m compileall -q jarvis/src` passed; `git diff --check` passed. No live authorization retry, browser open, socket, network/provider call, real keyring mutation, commit, or push was performed.

    ## OAuth live transport/save error classification hardening

    - **Status:** completed as a narrow offline OAuth correction.
    - **Behavior:** malformed JSON/value failures in the live urllib token transport now return a bounded `INVALID_RESPONSE` transport failure instead of falling through to generic `PROVIDER_ERROR`. Unexpected token-store save exceptions now map to `STORAGE_UNAVAILABLE` without exposing exception text, token material, client IDs, or authorization codes. Existing HTTP status categories, `invalid_grant` cleanup, and fail-closed behavior remain unchanged.
    - **TDD evidence:** RED: two focused regression tests failed (`2 failed, 71 deselected`), showing malformed live JSON became `PROVIDER_ERROR` and save exceptions escaped. GREEN: both focused tests passed (`2 passed, 71 deselected`).
    - **Validation:** `jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_oauth.py` → `73 passed`; `jarvis/.venv/bin/python -m compileall -q jarvis/src` → exit 0; `git diff --check` → exit 0. No live retry, browser, socket, network/provider call, real keyring mutation, commit, or push was performed.

    ## Confirmed OAuth production-adapter corrections

    - **Status:** completed as a narrow correction for the frozen HTTP response adapter and idempotent credential-marker cleanup.
    - **Behavior:** `_HTTPResponse` now uses declared frozen dataclass fields with a hidden payload and preserves `.json()`. Production `_urllib_transport` tests use only a patched `urllib.request.urlopen`, covering successful token exchange/store, `invalid_grant`, and typed HTTP status categories. `KeyringCredentialStore.save()` checks marker presence before deletion, while read/delete failures remain `STORAGE_UNAVAILABLE`; durable disable remains intact.
    - **TDD evidence:** RED: focused OAuth tests failed with six failures: `FrozenInstanceError` for `_HTTPResponse`, production transport results masked as `provider_error`, and strict missing-marker save returned `storage_unavailable`. GREEN: focused OAuth suite passed (`81 passed`). TRIANGULATE: focused OAuth/CLI suite passed (`99 passed`), including strict missing/present marker and failure cases, production transport HTTP errors, and payload repr redaction. REFACTOR: changes remain limited to the existing production adapter/store seams; no authorization policy or diagnostics were broadened.
    - **Validation:** `jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_oauth.py jarvis/tests/unit/test_cli.py` → `99 passed`; `jarvis/.venv/bin/python -m compileall -q jarvis/src` → exit 0; `git diff --check` → exit 0. No live authorization, browser, network, provider call, or real keyring access was performed; no authorization success is claimed.
    - **Diff:** `150 insertions, 5 deletions` across source and focused tests before this progress entry; progress evidence is additionally updated.

## Spotify Desktop target enrollment fingerprint correction

- **Status:** completed as a bounded offline correction to the verified playback policy and CLI enrollment boundary.
- **Behavior:** API device `id` values are validated in memory and transformed with a domain-separated SHA-256 fingerprint; policy compares with `hmac.compare_digest`, requires `type=computer`, and retains exactly-one matching semantics. `spotify target setup` requires enabled/authorized OAuth and one local `spotify` MPRIS identity, displays only bounded sanitized metadata, requires explicit confirmation/ordinal selection, and atomically persists only the derived fingerprint.
- **Safety:** invalid, ambiguous, declined, cancelled, malformed, or provider-failure paths perform no configuration write. Device IDs, payloads, and tokens are not printed, logged, or persisted. No live enrollment, playback, browser, network, or real keyring operation was executed.
- **TDD evidence:** RED: playback focused collection failed because the fingerprint helper was absent. GREEN: focused playback/config/CLI tests passed (`55 passed`). TRIANGULATE: full suite passed (`1276 passed, 3 deselected`), including no-ID-leakage and no-write cancellation coverage; compileall and diff checks passed. REFACTOR: the existing OAuth bridge and trusted `.env` boundary were reused without fallback, transfer, switching, or playback changes.
- **Validation:** `jarvis/.venv/bin/python -m compileall -q jarvis/src` and `git diff --check` passed. No commit or push was performed.

## Provider device-type mismatch correction

- **Status:** completed as a strict-TDD offline correction within the enrollment/playback surfaces.
- **Behavior:** Added one shared normalizer mapping Spotify's exact provider value `Computer` to internal `computer`. The legacy lowercase spelling is retained solely for existing offline fixtures; arbitrary case variants, `Smartphone`, `Speaker`, and unknown values remain rejected. Enrollment and `PlaybackPolicy` now use the same normalization before fingerprint comparison; hashing, redaction, confirmation, and all readiness gates remain unchanged.
- **TDD evidence:** RED: focused tests failed 7 cases, including standard `Computer` acceptance in policy/enrollment and the new non-computer CLI cases. GREEN: focused playback/CLI tests passed (`46 passed`). TRIANGULATE: the focused rejection matrix covers provider non-computer values and case variants; full pytest passed (`1287 passed, 3 deselected`). REFACTOR: normalization is centralized and no target-policy broadening or fallback was introduced.
- **Validation:** `jarvis/.venv/bin/python -m compileall -q jarvis/src` and `git diff --check` passed. No network/provider/playback/keyring/real-environment mutation, commit, or push was performed.

## Premium false-negative correction

- **Status:** completed for the bounded playback policy and OAuth bridge surfaces.
- **Behavior:** Removed the account-profile `/v1/me` and `product` gate; approved exact scopes, catalog selection, unique local Spotify MPRIS identity, configured fingerprint, and exact single `Computer` target match remain pre-play gates. Playback stays fixed-target with mandatory readback, without transfer or fallback. Only a bounded Spotify HTTP 403 category maps to `PREMIUM_REQUIRED`; unauthorized and other provider failures remain typed fail-closed, with provider payloads never exposed.
- **TDD evidence:** RED: focused playback/CLI collection failed because the new bounded playback error type was absent. GREEN: focused playback/CLI/OAuth tests passed (`132 passed`). TRIANGULATE: minimum-scope success/no-account-request, pre-play gate, 403 premium mapping, and 401 fail-closed coverage passed. REFACTOR: reused the existing OAuth result diagnostic seam and retained the uncommitted Computer device-type correction.
- **Validation:** Full pytest, compileall, and diff checks remain to be run; no live provider/network/playback/browser/keyring operation, commit, or push was performed.

## Spotify 204 empty playback response correction

- **Status:** completed as a strict-TDD offline correction to the production urllib transport and playback bridge boundary.
- **Behavior:** An empty response body is accepted only with exact HTTP 204 and represented as an empty payload; empty or malformed 200/other JSON responses return bounded `INVALID_RESPONSE`. OAuth token POST semantics and non-success HTTP diagnostics remain unchanged. The playback bridge treats the accepted PUT as an acceptance marker, while `PlaybackPolicy` still requires a matching subsequent readback before returning `OK`.
- **TDD evidence:** RED: new production-transport tests failed 2 cases because empty 204 became `None` and empty/malformed 200 returned `_HTTPResponse`. GREEN: focused transport/playback tests passed (`4 passed`). TRIANGULATE: existing unknown-readback and bounded-403 tests passed; payload redaction is covered. REFACTOR: the correction is limited to the existing transport failure and response seams.
- **Validation:** Focused OAuth/playback/CLI tests passed (`134 passed`); full pytest passed (`1292 passed, 3 deselected`); `jarvis/.venv/bin/python -m compileall -q jarvis/src` and `git diff --check` passed. No live provider/network/playback/browser/keyring/env mutation, commit, or push was performed.

## Spotify playback context readback correction

- **Status:** completed as a strict-TDD offline correction to playback readback verification.
- **Behavior:** Album/artist playback now requires the exact selected context URI in Spotify playback state's `context.uri` and the exact selected device ID. Track `item.uri`, missing context, alternate context, and alternate device never satisfy readback; existing redaction and readiness/fallback gates remain unchanged.
- **TDD evidence:** RED: focused playback tests failed 2 cases because the implementation compared the track item URI and accepted no context-based match. GREEN: focused playback suite passed (`25 passed`). TRIANGULATE: tests cover artist and album contexts with differing track items plus wrong device, missing context, and alternate context rejection. REFACTOR: changed only the existing readback predicate and focused playback fixtures/tests.
- **Validation:** `jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_playback.py` → `25 passed`; `jarvis/.venv/bin/pytest -q` → `1298 passed, 3 deselected`; `jarvis/.venv/bin/python -m compileall -q jarvis/src` → exit 0; `git diff --check` → exit 0.

## Playback request encoding correction

- **Status:** completed as a strict-TDD offline correction to the bounded urllib transport and playback bridge.
- **Behavior:** OAuth token POST remains form-urlencoded; supported GET requests carry query parameters without a body; the exact Spotify playback PUT carries `device_id` in the query and only `context_uri` as JSON with `application/json`, preserving authorization headers. Unsupported method/URL/content combinations fail closed. Playback still requires HTTP 204 acceptance normalization and matching readback before success.
- **TDD evidence:** RED: new request-inspection and playback-construction assertions failed because non-GET requests were form-encoded and `device_id` was sent in the JSON payload. GREEN: focused OAuth/playback tests passed after the narrow transport and bridge correction. TRIANGULATE: unsupported combinations, token form encoding, GET query/no-body, PUT JSON/header preservation, and 204/readback paths are covered without exposing identifiers, URIs, or tokens.
- **Validation:** Full pytest, compileall, and diff checks remain to be run; no live provider/network/playback/browser/keyring/env mutation, commit, or push was performed.

## Session checkpoint — 2026-09-14

- **Committed state:** `ce96190` is on `origin/main` and includes the completed verified desktop playback flow; preceding target enrollment is in `d526a1f`, interactive search/playback in `ef60b4f`, safe search in `0d33cb4`, and the production OAuth response fix in `ae12fa6`.
- **Verification:** the final combined source/test candidate passed `1298 passed, 3 deselected`; compileall and `git diff --check` passed before commit.
- **Live acceptance:** OAuth authorization completed successfully; a bounded `Abbey Road` album search returned five results; the local Spotify Desktop target was explicitly enrolled using only a persisted domain-separated SHA-256 fingerprint; `Abbey Road (Remastered)` by The Beatles played on the enrolled target; API readback confirmed the exact device and album context. No transfer, fallback device, arbitrary URI, or plaintext credential storage was used.
- **Repository state:** source, tests, and progress evidence through `ce96190` are committed and pushed. The local `.env` contains only the non-secret target fingerprint addition from enrollment and remains ignored by Git. OAuth credentials remain in the OS keyring.
- **OpenSpec status:** native status reports 21/24 rows complete. The broad user-authorization, OAuth, and catalog rows remain unchecked even though narrower checked rows and committed/live evidence cover their implementation. `verify-report.md` is stale/partial and `sync-report.md` is missing; sync/archive remain blocked.
- **Tomorrow's first action:** obtain explicit maintainer authorization to reset the SDD runtime objective for `jarvis-spotify-control`, then acquire a bounded reconciliation attempt, reconcile the three broad task rows against committed evidence, refresh verification, and only then consider sync/archive.
- **Runtime blocker:** attempt acquire stopped with `maintainer_decision` because the objective changed. The required expected ledger revision at this checkpoint is `sha256:3cab91f68435080714c59b413134d852b045cc9bc3ee5099e20bcdc068796df2`; re-read native status before any reset and never reuse this value blindly.
- **Native review limitation:** ordinary review remains blocked by `managed_assets_outdated`; no review approval or delivery authority is claimed.
