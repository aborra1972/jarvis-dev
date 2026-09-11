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
