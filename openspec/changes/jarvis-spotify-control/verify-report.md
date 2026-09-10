```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:6c0db51cc007ff141bc63532f464846e93c1e187e76c64e69f621814fb6471ea
verdict: fail
blockers: 1
critical_findings: 1
requirements: 0/8
scenarios: 0/19
test_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
test_exit_code: 0
test_output_hash: sha256:8abb40d3a08c320b5588899dba3bd6feec5e435c7b2beb42510e3bc70478c45b
build_command: ""
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# SDD Verification — corrected Stage 1 task 1.2.1

## Status

**FAIL for whole-change/archive readiness; PASS for the corrected task 1.2.1 adapter slice.** The prior fail-closed defect is corrected: a nonzero `playerctl -l` result is rejected before stdout identity parsing and cannot lead to play/pause control.

## Scope and artifacts reviewed

- `openspec/changes/jarvis-spotify-control/specs/spotify-control/spec.md`
- `openspec/changes/jarvis-spotify-control/design.md`
- `openspec/changes/jarvis-spotify-control/tasks.md`
- `openspec/changes/jarvis-spotify-control/apply-progress.md`
- `jarvis/src/jarvis/services/spotify.py`
- `jarvis/tests/unit/test_spotify_local.py`
- `openspec/config.yaml`

No source or test files were edited by verification. Only this existing OpenSpec verify report is updated.

## Corrected task 1.2.1 findings

- **Nonzero probe fail-closed: PASS.** `probe.returncode != 0` returns `SpotifyErrorCode.MPRIS_UNAVAILABLE` before parsing `probe.stdout`; the focused regression test supplies Spotify-looking output and asserts exactly one probe call, with no control invocation and no success.
- **Fixed argv: PASS.** Calls are exactly `playerctl -l`, `playerctl --player=spotify play|pause`, and `playerctl --player=spotify status`.
- **Spotify-only identity: PASS.** Exact configured identity matching requires exactly one match; zero, duplicate, or non-Spotify listings fail closed without control.
- **Timeout and cancellation: PASS.** Every subprocess call uses `shell=False`, captured text, `check=False`, and the configured bounded timeout. Cancellation is checked before probe, before control, after subprocess boundaries, and before return; cancellation prevents late success.
- **Post-state fail-closed: PASS.** Nonzero or mismatching status returns `STATE_UNKNOWN`; successful control is not claimed without the requested state.
- **Safe errors: PASS.** Typed categories are returned without raw stderr or command details.

The adapter remains credential-free, network-free, and separate from generic `execute`; registry, lifecycle, diagnostics, and Stage 2 surfaces remain outside this task slice.

## Spec coverage

The adapter directly exercises the local-control portions of the Stage 1 specification and design, including unique Spotify identity, fixed command boundaries, bounded execution, cancellation, and post-state verification. Full requirement/scenario coverage is not claimed because service dispatch, lifecycle integration, diagnostics, and all later Stage 2 work remain incomplete.

## Task completion and workload

Task 1.2.1 is checked `[x]` and its correction evidence is present in `apply-progress.md`. The exact corrected regression test is present and substantive. Twelve implementation tasks remain unchecked, so the change is not ready for archive and the full SDD verdict remains `fail`:

```text
- [ ] Add the Stage 1 service dispatch and registry wiring in `jarvis/src/jarvis/actions/base.py` plus focused tests in `jarvis/tests/unit/test_spotify_service.py` and `jarvis/tests/unit/test_actions_base.py`; ensure only validated Spotify intents reach the adapter, no generic `execute` route is used, and spoken results are accurate/recoverable for disabled, missing, ambiguous, failed, cancelled, stale, and unknown-state outcomes. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED verifies handler isolation and every safe error mapping; GREEN wires the dedicated handler; TRIANGULATE checks registry dispatch with fake sessions and unchanged handlers for `open_app`/`execute`; REFACTOR keeps policy in the domain boundary rather than the generic executor. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 1 lifecycle handling with `jarvis/src/jarvis/orchestrator/loop.py` and `jarvis/src/jarvis/orchestrator/contracts.py`; add tests in `jarvis/tests/unit/test_loop.py` (or a focused lifecycle test module) for off precedence, epoch replacement, cancellation during a blocked probe/control, readiness barriers, late-result suppression, conversation behavior, TTS/microphone safety, and existing confirmation semantics. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED reproduces side effects or spoken success after invalidation; GREEN adds operation-context propagation and stale-result rejection; TRIANGULATE runs fake blocked adapters through the FSM and the full required pytest command; REFACTOR preserves existing loop behavior and minimizes lifecycle-specific branching. <!-- sdd-owner: implementation -->
- [ ] Extend `jarvis/src/jarvis/diagnose.py` with safe local Spotify capability diagnostics and document Stage 1 commands/boundaries in `jarvis/docs/comandos_jarvis.md` (or the repository's selected command guide); add tests in `jarvis/tests/unit/test_diagnose.py` asserting no raw output or arguments leak. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED asserts missing/ambiguous capability and redaction failures; GREEN emits normalized actionable status; TRIANGULATE checks fake diagnostics plus an opt-in host probe; REFACTOR keeps existing diagnostics and `open_app` semantics unchanged. <!-- sdd-owner: implementation -->
- [ ] Run a Stage 1 acceptance pass with no network and no Spotify credentials, including deterministic unit tests and optional Linux-marked playerctl/MPRIS tests; record the exact command `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q`, the capability-spike result, and rollback boundary (unregister Spotify intents/service while retaining `open_app`). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the offline/no-credentials acceptance baseline before implementation; GREEN is the passing Stage 1 suite; TRIANGULATE is host probe plus regression suite; REFACTOR is the reviewed independent Stage 1 release slice. <!-- sdd-owner: implementation -->
- [ ] **User authorization gate:** before creating Spotify developer credentials, registering an application, adding OAuth configuration, or making any OAuth/API call, stop and obtain explicit user authorization for the external integration, redirect setup, approved scopes (`user-read-playback-state` and `user-modify-playback-state` only), and Premium requirement; record the decision in the change notes. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a test/guard proving Stage 2 cannot initialize when opt-in or authorization is absent; GREEN is the explicit gate state; TRIANGULATE verifies a clean environment and Stage 1 operation remain network/secret-free; REFACTOR makes the gate auditable and non-bypassable. <!-- sdd-owner: implementation -->
- [ ] Implement OAuth Authorization Code with PKCE, protected OS-keyring-only storage, refresh single-flight, expiry/revocation/disable cleanup, callback state validation, and redaction at concrete targets `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/config.py`, and focused tests `jarvis/tests/unit/test_spotify_oauth.py`; never add plaintext fallback or expose tokens/codes/verifiers in logs, history, prompts, TTS, URLs, or errors. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers absent opt-in, state mismatch, storage failure, refresh rotation, invalid grant, revoke deletion, and secret leakage; GREEN adds the minimum PKCE/keyring lifecycle; TRIANGULATE uses fake callback/API/keyring plus log/history/TTS redaction scans; REFACTOR isolates provider details and keeps Stage 1 credential-free. <!-- sdd-owner: implementation -->
- [ ] Add authorized album/artist catalog contracts and normalization at `jarvis/src/jarvis/services/spotify.py` (split catalog client if necessary) with tests in `jarvis/tests/unit/test_spotify_catalog.py`: bounded query/results, official search endpoint only, no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, replacement/TTL/off/cancellation invalidation, and no playback during search or ambiguity. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported kinds, oversized queries, empty/multiple results, expired/mismatched selections, and accidental playback; GREEN implements normalized candidates and mandatory clarification; TRIANGULATE exercises fake HTTP, clock, session lifecycle, and redaction; REFACTOR discards raw provider payloads. <!-- sdd-owner: implementation -->
- [ ] Extend validated intent prompts/patterns and dispatch for `spotify_search` and `spotify_play_selection` in `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/interpreter/golden.py`, and `jarvis/src/jarvis/actions/base.py`; add tests in `jarvis/tests/unit/test_spotify_intents.py` proving numbers/exact pending references are the only clarification selectors and arbitrary URI/device/entity data cannot cross the boundary. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported playlist/recommendation/track/account requests and LLM-injected backend fields; GREEN adds constrained routing; TRIANGULATE combines deterministic Spanish forms, malformed provider-like payloads, and registry tests; REFACTOR preserves generic `execute` rejection and existing interpretation caches. <!-- sdd-owner: implementation -->
- [ ] Implement Premium/account/device readiness and playback policy in `jarvis/src/jarvis/services/spotify.py` with tests in `jarvis/tests/unit/test_spotify_playback.py`: require valid scopes and Premium, verify local Spotify identity plus exactly one configured desktop fingerprint, source URI only from current pending candidates, use bounded playback/readback, and fail closed for missing/ambiguous/unplayable/unknown targets without transfer, Connect fallback, device switching, browser automation, or MPRIS fallback. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers every policy gate and asserts no playback call on failure; GREEN adds one-target playback and state verification; TRIANGULATE uses fake Web API plus local identity and cancellation races; REFACTOR separates policy from transport and retains typed safe errors. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 2 status/error speech, diagnostics, history/log redaction, and lifecycle cancellation in `jarvis/src/jarvis/actions/base.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/diagnose.py`, and `jarvis/src/jarvis/orchestrator/logs.py`; add regression tests covering unauthorized, expired, revoked, storage unavailable, timeout, Premium failure, target failure, clarification, off, goodbye, stale result, TTS/microphone barriers, and unchanged destructive/open-app paths. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED demonstrates leaked/late/incorrect success paths; GREEN maps safe typed outcomes through the existing FSM; TRIANGULATE runs full offline regression plus fake API/keyring and lifecycle tests; REFACTOR centralizes redaction and preserves existing safety gates. <!-- sdd-owner: implementation -->
- [ ] Document OAuth consent, minimum scopes, Premium requirement, local-only versus networked behavior, clarification rules, target restrictions, disable/revoke procedure, and rollback in `jarvis/docs/comandos_jarvis.md` and the change notes; verify no secrets or raw catalog data appear in repository artifacts. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a documentation/privacy review finding missing gates or secret-like material; GREEN is complete user-facing guidance; TRIANGULATE checks docs against spec/design and redaction tests; REFACTOR removes ambiguous language and keeps Stage 1 instructions independently usable. <!-- sdd-owner: implementation -->
- [ ] Run the complete required pytest command and an explicitly authorized, bounded integration smoke test only if credentials, keyring, network, Premium account, Spotify Desktop, and the configured target are all available; record results, known limitations, and the Stage 2 rollback (disable/revoke and delete keyring material without changing Stage 1). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the pre-release failure matrix; GREEN is deterministic suite plus authorized smoke success/failure classification; TRIANGULATE compares provider responses with policy fakes and verifies no fallback device; REFACTOR closes test isolation and release-readiness defects without adding scope. <!-- sdd-owner: implementation -->
```

The remaining eight Stage 2 task lines (authorization, OAuth, catalog/intents, playback, integration, documentation, and release verification) are also unchecked at lines 57–73 of `tasks.md` and remain out of scope. Review workload remains bounded for this slice (245 authored changed lines reported in apply-progress, below the 350-line slice limit); the forecasted overall feature still recommends chained PRs.

## Tests and validation

Focused command:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_local.py
```

Result: exit 0, `8 passed in 0.07s`; output hash `sha256:3247c50c34e782db19f552455bce1f096e033aae5010deec64401bb0f5ec19c`.

Required full command:

```text
cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
```

Result: exit 0, `1040 passed, 1 warning in 53.29s`; output hash `sha256:8abb40d3a08c320b5588899dba3bd6feec5e435c7b2beb42510e3bc70478c45b`. The warning is the existing unknown `e2e` mark at `jarvis/tests/e2e/test_e2e_smoke.py:30`.

No build command is configured. No host control action, network call, credential access, or destructive operation was performed.

## Strict TDD compliance

Strict TDD is active. `apply-progress.md` records the correction's RED test, GREEN guard, TRIANGULATE focused/full evidence, and REFACTOR review. The actual regression test exists and asserts the critical safety property: Spotify-looking stdout on a nonzero probe produces no control call and no success. Existing fixed-argv, Spotify-only, timeout/cancellation, and post-state tests remain green.

## Structured status and action context

Artifact store is OpenSpec with repository `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; action context is repo-local and the authorized edit root is that repository. Required spec, design, tasks, and apply-progress artifacts are present. The active task slice is complete, while twelve later implementation rows remain unchecked. No ownership or edit-root warning was found.

## Exact blocker

1. Twelve implementation-owned task rows remain unchecked; this is a CRITICAL completeness/archive blocker for the overall change, although it does not invalidate corrected task 1.2.1.

## Key Learnings

1. A capability probe must reject nonzero exit status before trusting identity output.
2. Fixed argv and exact identity matching still require post-action state verification.
