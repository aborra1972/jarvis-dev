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
