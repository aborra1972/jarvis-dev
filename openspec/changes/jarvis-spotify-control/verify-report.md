```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:c7fc218c0b9c405a6e142eea90f0e7169dc98254afdf7a6166627c10f11b7bc5
verdict: fail
blockers: 8
critical_findings: 8
requirements: 4/8
scenarios: 9/19
test_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
test_exit_code: 0
test_output_hash: sha256:77af3fbe9c8efcfa899cae79ba9b5f003b50e8d3fb7a7b56ebe04b601cee60d8
build_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# SDD Verification — `jarvis-spotify-control`

## Status

**BOUNDED OFFLINE CATALOG/CLARIFICATION SLICE PASS; OVERALL CHANGE FAIL.** The authorized work unit `spotify-stage2-catalog-clarification-verify` is verified read-only and offline. The overall change is not archive-ready because eight implementation-owned task rows remain unchecked.

## Scope and safety

- Canonical repository: `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`.
- Verified only the bounded catalog/clarification slice and its OAuth/PKCE preservation boundary.
- Source and tests were read-only. No source/test edits, secrets, browser, sockets, network, token exchange, live provider, or playback were used.
- Existing unrelated working-tree changes, including `.atl` files, were preserved.

## Catalog contract coverage

- `CatalogClient` uses only injected provider calls and the official `https://api.spotify.com/v1/search` endpoint.
- Album/artist kinds are allowlisted; query text is trimmed and bounded to 100 characters; requested results are clamped to 1–10; transport timeout is bounded at 5 seconds.
- Empty, single, and multiple provider results normalize to safe `CatalogResult` values; malformed items are discarded; raw provider payloads are not retained; search never invokes playback.
- Selection IDs are generated opaque values, held only in memory, bound to the session, expire by injected clock/TTL, resolve once, and are invalidated by replacement, explicit invalidation (`off`), and cancellation.
- Session mismatch, expired, replaced, consumed, and cancelled selections fail closed.
- Lifecycle wiring, live transport, catalog intents, and playback are intentionally outside this bounded slice and were not claimed.

## OAuth/PKCE preservation

Focused OAuth tests remain GREEN. The existing offline OAuth boundary preserves fixed approved scopes, S256 PKCE, keyring-only storage, protected/redacted token representations, expiry/refresh/revoke/disable behavior, and exact loopback callback state/session/expiry/one-time validation. No browser, listener, socket, network, or token exchange was invoked by verification.

## Task completion and workload

The dedicated catalog safe-slice row is checked and has apply evidence with RED → GREEN → TRIANGULATE → REFACTOR. The broad catalog implementation row remains unchecked, as do seven other implementation rows. Per SDD policy, every unchecked implementation row is a critical archive blocker.

Exact unchecked implementation task lines:

- [ ] **User authorization gate:** before creating Spotify developer credentials, registering an application, adding OAuth configuration, or making any OAuth/API call, stop and obtain explicit user authorization for the external integration, redirect setup, approved scopes (`user-read-playback-state` and `user-modify-playback-state` only), and Premium requirement; record the decision in the change notes. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a test/guard proving Stage 2 cannot initialize when opt-in or authorization is absent; GREEN is the explicit gate state; TRIANGULATE verifies a clean environment and Stage 1 operation remain network/secret-free; REFACTOR makes the gate auditable and non-bypassable. <!-- sdd-owner: implementation -->
- [ ] Implement OAuth Authorization Code with PKCE, protected OS-keyring-only storage, refresh single-flight, expiry/revocation/disable cleanup, callback state validation, and redaction at concrete targets `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/config.py`, and focused tests `jarvis/tests/unit/test_spotify_oauth.py`; never add plaintext fallback or expose tokens/codes/verifiers in logs, history, prompts, TTS, URLs, or errors. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers absent opt-in, state mismatch, storage failure, refresh rotation, invalid grant, revoke deletion, and secret leakage; GREEN adds the minimum PKCE/keyring lifecycle; TRIANGULATE uses fake callback/API/keyring plus log/history/TTS redaction scans; REFACTOR isolates provider details and keeps Stage 1 credential-free. <!-- sdd-owner: implementation -->
- [ ] Add authorized album/artist catalog contracts and normalization at `jarvis/src/jarvis/services/spotify.py` (split catalog client if necessary) with tests in `jarvis/tests/unit/test_spotify_catalog.py`: bounded query/results, official search endpoint only, no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, replacement/TTL/off/cancellation invalidation, and no playback during search or ambiguity. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported kinds, oversized queries, empty/multiple results, expired/mismatched selections, and accidental playback; GREEN implements normalized candidates and mandatory clarification; TRIANGULATE exercises fake HTTP, clock, session lifecycle, and redaction; REFACTOR discards raw provider payloads. <!-- sdd-owner: implementation -->
- [ ] Extend validated intent prompts/patterns and dispatch for `spotify_search` and `spotify_play_selection` in `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/interpreter/golden.py`, and `jarvis/src/jarvis/actions/base.py`; add tests in `jarvis/tests/unit/test_spotify_intents.py` proving numbers/exact pending references are the only clarification selectors and arbitrary URI/device/entity data cannot cross the boundary. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported playlist/recommendation/track/account requests and LLM-injected backend fields; GREEN adds constrained routing; TRIANGULATE combines deterministic Spanish forms, malformed provider-like payloads, and registry tests; REFACTOR preserves generic `execute` rejection and existing interpretation caches. <!-- sdd-owner: implementation -->
- [ ] Implement Premium/account/device readiness and playback policy in `jarvis/src/jarvis/services/spotify.py` with tests in `jarvis/tests/unit/test_spotify_playback.py`: require valid scopes and Premium, verify local Spotify identity plus exactly one configured desktop fingerprint, source URI only from current pending candidates, use bounded playback/readback, and fail closed for missing/ambiguous/unplayable/unknown targets without transfer, Connect fallback, device switching, browser automation, or MPRIS fallback. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers every policy gate and asserts no playback call on failure; GREEN adds one-target playback and state verification; TRIANGULATE uses fake Web API plus local identity and cancellation races; REFACTOR separates policy from transport and retains typed safe errors. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 2 status/error speech, diagnostics, history/log redaction, and lifecycle cancellation in `jarvis/src/jarvis/actions/base.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/diagnose.py`, and `jarvis/src/jarvis/orchestrator/logs.py`; add regression tests covering unauthorized, expired, revoked, storage unavailable, timeout, Premium failure, target failure, clarification, off, goodbye, stale result, TTS/microphone barriers, and unchanged destructive/open-app paths. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED demonstrates leaked/late/incorrect success paths; GREEN maps safe typed outcomes through the existing FSM; TRIANGULATE runs full offline regression plus fake API/keyring and lifecycle tests; REFACTOR centralizes redaction and preserves existing safety gates. <!-- sdd-owner: implementation -->
- [ ] Document OAuth consent, minimum scopes, Premium requirement, local-only versus networked behavior, clarification rules, target restrictions, disable/revoke procedure, and rollback in `jarvis/docs/comandos_jarvis.md` and the change notes; verify no secrets or raw catalog data appear in repository artifacts. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a documentation/privacy review finding missing gates or secret-like material; GREEN is complete user-facing guidance; TRIANGULATE checks docs against spec/design and redaction tests; REFACTOR removes ambiguous language and keeps Stage 1 instructions independently usable. <!-- sdd-owner: implementation -->
- [ ] Run the complete required pytest command and an explicitly authorized, bounded integration smoke test only if credentials, keyring, network, Premium account, Spotify Desktop, and the configured target are all available; record results, known limitations, and the Stage 2 rollback (disable/revoke and delete keyring material without changing Stage 1). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the pre-release failure matrix; GREEN is deterministic suite plus authorized smoke success/failure classification; TRIANGULATE compares provider responses with policy fakes and verifies no fallback device; REFACTOR closes test isolation and release-readiness defects without adding scope. <!-- sdd-owner: implementation -->

## Structured status and action context

Native matching status was consumed for `jarvis-spotify-control`: `store: openspec`, canonical workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`, `actionContext.mode: repo-local`, allowed edit root is the canonical repository, `apply: ready`, `verify: blocked` pending rerun, and `nextRecommended: apply`. The status is authoritative for this file-backed OpenSpec session. The parent supplied the matching native attempt for this exact work unit; no second attempt was acquired.

## Validation commands

- Focused catalog/OAuth: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_catalog.py jarvis/tests/unit/test_spotify_oauth.py` — 38 passed, exit 0; output hash `sha256:56ea348f1fc76e5c0c1cafd78ff8dba7d8e5696f5b8677c26c42362ab2d8b9c7`.
- Full pytest: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q` — 1097 passed, 3 deselected, exit 0; output hash `sha256:77af3fbe9c8efcfa899cae79ba9b5f003b50e8d3fb7a7b56ebe04b601cee60d8`.
- Compile: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src` — exit 0; output hash `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Diff check: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && git diff --check` — exit 0; output hash `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

## Strict TDD and review workload

`openspec/config.yaml` confirms strict TDD. The apply-progress artifact contains RED → GREEN → TRIANGULATE → REFACTOR evidence for the catalog safe slice and its focused tests exist and remain GREEN. Assertions cover contract outcomes, endpoint bounds, session/TTL/one-time invalidation, malformed payload rejection, and no playback calls; no tautological or smoke-only assertion was identified. No chained-PR boundary was claimed beyond the explicitly authorized bounded slice; the broader high-risk forecast remains unresolved and no size exception was inferred.

## Exact blockers

1. Eight unchecked implementation-owned task rows remain, including the broad OAuth and broad catalog rows.
2. Catalog intents, lifecycle integration, Premium/desktop playback policy, documentation/release verification, and live integration are intentionally outside this slice and cannot be claimed.

status: fail
executive_summary: The bounded offline catalog/clarification slice passes focused catalog/OAuth tests, full pytest, compileall, and diff check with no live side effects; overall verification remains blocked by eight unchecked implementation tasks.
artifacts: openspec/changes/jarvis-spotify-control/verify-report.md
next_recommended: sdd-apply
risks: Broad OAuth, catalog intent routing, playback policy, lifecycle integration, and release verification remain incomplete; no live provider or playback acceptance is claimed.
skill_resolution: fallback-path

## Key Learnings

1. Injected catalog boundaries can verify official endpoint shape, bounded results, and ambiguity safety without network access.
2. Opaque session-bound selections prevent stale or cross-session catalog choices from reaching playback.
3. A passing safe slice does not complete the broader Stage 2 implementation task.
