```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:8b5a7d6d195f4a808818da8f1f0be77ad25cdc19f2d33da73884b75ae6c0a5db
verdict: fail
blockers: 7
critical_findings: 7
requirements: 4/8
scenarios: 9/19
test_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
test_exit_code: 0
test_output_hash: sha256:93afc57b991f68d4820b18056e96cbb1da44fcd97839582f911f937e5b72bafa
build_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# SDD Verification — `jarvis-spotify-control`

## Status

**BOUNDED WORK UNIT PASS; OVERALL CHANGE FAIL.** `spotify-stage2-search-selection-intents` is verified read-only and offline. The bounded implementation is correct for its stated slice, but the overall change is not archive-ready because seven implementation-owned task rows remain unchecked.

## Scope and safety

- Canonical repository: `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`.
- Verified only `spotify-stage2-search-selection-intents` (task 2.2.2) and preservation of catalog/OAuth/PKCE/callback/Stage 1 boundaries.
- No source/test edits, commit, push, network, secrets, browser, sockets, token exchange, live provider, or playback were used.
- Existing unrelated working-tree changes were preserved.

## Verified bounded behavior

- `spotify_search` accepts only album/artist plus bounded query; deterministic Spanish forms normalize to the dedicated intent.
- `spotify_play_selection` accepts numeric ordinal selectors or opaque pending references only; URI, device, provider, unsupported media, and arbitrary extra entity fields are rejected by schema validation.
- Search and selection use the injected catalog boundary only; no generic `execute` route or playback call is introduced. Returned data is limited to safe selection ID, kind, and name.
- LLM-produced intent payloads remain schema-validated; `interpreter.py` was inspected and required no change.
- Existing catalog normalization/invalidation and OAuth PKCE/keyring/callback seams remain unchanged by this work unit.

## Task completion and exact unchecked implementation rows

Task 2.2.2 is checked and its apply-progress evidence records RED → GREEN → TRIANGULATE → REFACTOR. The following seven implementation-owned rows remain unchecked and are critical archive blockers:

- [ ] **User authorization gate:** before creating Spotify developer credentials, registering an application, adding OAuth configuration, or making any OAuth/API call, stop and obtain explicit user authorization for the external integration, redirect setup, approved scopes (`user-read-playback-state` and `user-modify-playback-state` only), and Premium requirement; record the decision in the change notes. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a test/guard proving Stage 2 cannot initialize when opt-in or authorization is absent; GREEN is the explicit gate state; TRIANGULATE verifies a clean environment and Stage 1 operation remain network/secret-free; REFACTOR makes the gate auditable and non-bypassable. <!-- sdd-owner: implementation -->
- [ ] Implement OAuth Authorization Code with PKCE, protected OS-keyring-only storage, refresh single-flight, expiry/revocation/disable cleanup, callback state validation, and redaction at concrete targets `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/config.py`, and focused tests `jarvis/tests/unit/test_spotify_oauth.py`; never add plaintext fallback or expose tokens/codes/verifiers in logs, history, prompts, TTS, URLs, or errors. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers absent opt-in, state mismatch, storage failure, refresh rotation, invalid grant, revoke deletion, and secret leakage; GREEN adds the minimum PKCE/keyring lifecycle; TRIANGULATE uses fake callback/API/keyring plus log/history/TTS redaction scans; REFACTOR isolates provider details and keeps Stage 1 credential-free. <!-- sdd-owner: implementation -->
- [ ] Add authorized album/artist catalog contracts and normalization at `jarvis/src/jarvis/services/spotify.py` (split catalog client if necessary) with tests in `jarvis/tests/unit/test_spotify_catalog.py`: bounded query/results, official search endpoint only, no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, replacement/TTL/off/cancellation invalidation, and no playback during search or ambiguity. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported kinds, oversized queries, empty/multiple results, expired/mismatched selections, and accidental playback; GREEN implements normalized candidates and mandatory clarification; TRIANGULATE exercises fake HTTP, clock, session lifecycle, and redaction; REFACTOR discards raw provider payloads. <!-- sdd-owner: implementation -->
- [ ] Implement Premium/account/device readiness and playback policy in `jarvis/src/jarvis/services/spotify.py` with tests in `jarvis/tests/unit/test_spotify_playback.py`: require valid scopes and Premium, verify local Spotify identity plus exactly one configured desktop fingerprint, source URI only from current pending candidates, use bounded playback/readback, and fail closed for missing/ambiguous/unplayable/unknown targets without transfer, Connect fallback, device switching, browser automation, or MPRIS fallback. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers every policy gate and asserts no playback call on failure; GREEN adds one-target playback and state verification; TRIANGULATE uses fake Web API plus local identity and cancellation races; REFACTOR separates policy from transport and retains typed safe errors. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 2 status/error speech, diagnostics, history/log redaction, and lifecycle cancellation in `jarvis/src/jarvis/actions/base.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/diagnose.py`, and `jarvis/src/jarvis/orchestrator/logs.py`; add regression tests covering unauthorized, expired, revoked, storage unavailable, timeout, Premium failure, target failure, clarification, off, goodbye, stale result, TTS/microphone barriers, and unchanged destructive/open-app paths. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED demonstrates leaked/late/incorrect success paths; GREEN maps safe typed outcomes through the existing FSM; TRIANGULATE runs full offline regression plus fake API/keyring and lifecycle tests; REFACTOR centralizes redaction and preserves existing safety gates. <!-- sdd-owner: implementation -->
- [ ] Document OAuth consent, minimum scopes, Premium requirement, local-only versus networked behavior, clarification rules, target restrictions, disable/revoke procedure, and rollback in `jarvis/docs/comandos_jarvis.md` and the change notes; verify no secrets or raw catalog data appear in repository artifacts. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a documentation/privacy review finding missing gates or secret-like material; GREEN is complete user-facing guidance; TRIANGULATE checks docs against spec/design and redaction tests; REFACTOR removes ambiguous language and keeps Stage 1 instructions independently usable. <!-- sdd-owner: implementation -->
- [ ] Run the complete required pytest command and an explicitly authorized, bounded integration smoke test only if credentials, keyring, network, Premium account, Spotify Desktop, and the configured target are all available; record results, known limitations, and the Stage 2 rollback (disable/revoke and delete keyring material without changing Stage 1). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the pre-release failure matrix; GREEN is deterministic suite plus authorized smoke success/failure classification; TRIANGULATE compares provider responses with policy fakes and verifies no fallback device; REFACTOR closes test isolation and release-readiness defects without adding scope. <!-- sdd-owner: implementation -->

## Structured status and actionContext

Native status was consumed from the canonical repository with `store: openspec`, repo-local action context, workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`, and allowed edit root equal to that workspace. Native status reports `apply: ready`, `verify: blocked` because prior verification evidence is incomplete, `archive: blocked`, task progress `14/21 complete`, and `nextRecommended: apply`. Parent supplied the current native verify attempt for this bounded work unit; this verification did not acquire a second attempt. The status is authoritative for the file-backed OpenSpec session.

## Validation commands

- Focused intent/catalog/OAuth: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_intents.py jarvis/tests/unit/test_spotify_catalog.py jarvis/tests/unit/test_spotify_oauth.py` — 53 passed, exit 0; output hash `sha256:9a7a076e05094be08940a902c16e04d3f085e1f2d189a9ab23b32b989fe38a77`.
- Full pytest: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q` — 1112 passed, 3 deselected, exit 0; output hash `sha256:93afc57b991f68d4820b18056e96cbb1da44fcd97839582f911f937e5b72bafa`.
- Compile: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src` — exit 0; output hash `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Diff check: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && git diff --check` — exit 0; output hash `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Strict TDD and workload

Strict TDD is active. Apply-progress records RED, GREEN, TRIANGULATE, and REFACTOR evidence for this slice; focused assertions cover deterministic forms, schema rejection, safe dispatch, and no generic execution. The bounded implementation/test scope is within the authorized review slice. Chaining remains appropriate for the broader feature; no size exception was inferred.

## Exact blockers

1. Seven unchecked implementation-owned task rows remain; archive and overall verification cannot be clean.
2. OAuth authorization gate completion, broad catalog integration, playback policy, lifecycle/error integration, documentation, and release verification remain outside this work unit and unverified.

status: fail
executive_summary: The bounded spotify-stage2-search-selection-intents work unit passes focused intent/catalog/OAuth tests, full pytest, compileall, and diff check without external side effects; overall verification remains blocked by seven unchecked implementation tasks.
artifacts: openspec/changes/jarvis-spotify-control/verify-report.md
next_recommended: sdd-apply
risks: Broader OAuth authorization, catalog completion, playback policy, lifecycle integration, documentation, and release verification remain incomplete; no live provider or playback acceptance is claimed.
skill_resolution: fallback-path

## Key Learnings

1. Schema validation and deterministic golden routing jointly constrain Spotify selection data before catalog dispatch.
2. Injected offline tests can preserve OAuth PKCE callback and catalog boundaries without network or provider access.
3. A verified bounded work unit does not make the parent OpenSpec change archive-ready while implementation tasks remain unchecked.

## Current documentation/reconciliation slice

**Status: bounded documentation and reconciliation complete; overall change remains incomplete.**

This current entry supersedes the stale task accounting above without deleting
the historical verification record. The committed implementation slice at
`eb38937` was independently verified before this documentation pass: 93 focused
tests, 1127 full-suite tests, compileall, and `git diff --check` passed. The
current work checks only task rows 2.3.2 and 2.4's documentation row. Four
implementation-owned rows remain unchecked, including broad OAuth/catalog work
and the separate release-verification row; no live Spotify or native SDD
verification is claimed.

The native SDD ledger was not used as verification authority because its
intended-untracked metadata is stale: it refers to a playback test that is
already tracked. This is the explicitly authorized project-local reconciliation
exception. No source, tests, proposal/spec/design, `.atl`, credentials, or
unrelated files were changed.

### Documentation/privacy TDD evidence

- **RED:** the documentation/privacy review identified missing explicit opt-in,
  exact-scope, Premium, network-boundary, target, clarification, rollback, and
  secret-handling guidance.
- **GREEN:** `jarvis/docs/comandos_jarvis.md` now documents those gates in
  concise Spanish, keeps Stage 1 independently usable, and states fail-closed
  behavior without fallback or automatic selection.
- **TRIANGULATE:** the wording was checked against `design.md` and the existing
  redaction/diagnostic/lifecycle evidence; no live Spotify or native SDD check
  was performed.
- **REFACTOR:** the section was kept additive and bounded, with Stage 1
  instructions preserved and ambiguous device/browser/fallback promises removed.

### Current validation evidence

The exact validation commands and results for this reconciliation are recorded
in `apply-progress.md`; no provider, network, credentials, or native SDD
verification was used.
