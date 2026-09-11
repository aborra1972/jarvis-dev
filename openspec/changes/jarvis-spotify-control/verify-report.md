```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d9582ef44bb34e872c7c4de9eccb7044012f5ced0b7fb7dd6aaec30518e802c4
verdict: fail
blockers: 8
critical_findings: 8
requirements: 4/8
scenarios: 9/19
test_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q
test_exit_code: 0
test_output_hash: sha256:8ffd7d07bcaba8943b3f90c35082bdae288fa16730ec3f3c3824357f7b6549b0
build_command: cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src
build_exit_code: 0
build_output_hash: sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

# SDD Verification — `jarvis-spotify-control`

## Verdict

**BOUNDED SLICE PASS; OVERALL CHANGE FAIL.** The authorized callback/state slice is implemented and passes focused and full offline verification. The OpenSpec change is not archive-ready because eight implementation-owned task rows remain unchecked, including the broad OAuth row.

## Scope and safety

- Canonical repository only: `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`.
- Verified only the bounded work unit `spotify-stage2-loopback-callback-state-verify`.
- Read-only source/test inspection; no source/test edits, commits, pushes, secrets, browser, sockets, network, API, token exchange, catalog, or playback were used.
- Existing unrelated working-tree changes were not modified.

## Callback/state evidence

- Exact redirect is `http://127.0.0.1:8888/callback`, reused for code exchange and parser validation.
- `parse_pkce_callback()` is a pure injected seam: it performs no I/O or live side effects.
- URL parsing requires exact scheme, host/port, path, no fragment, and exactly one non-empty `code` and `state`; extra or missing query content is rejected.
- Session binding, expiry, and one-time consumption are enforced before returning authorization code material.
- State uses `hmac.compare_digest`; verifier/state and authorization code representations are redacted from dataclass reprs. No callback listener or transport is present in this slice.
- Focused tests cover accepted parsing, redirect/query rejection, session mismatch, state mismatch, expiry, one-time consumption, and missing code.

## Tests and validation

- Focused OAuth: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q jarvis/tests/unit/test_spotify_oauth.py` — **30 passed**, exit 0; output hash `sha256:38ad026a445520b4a0b74c2e9c8b3946766c8d19a25177af8e9527e385f88f5f`.
- Full suite: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest -q` — **1089 passed, 3 deselected**, exit 0; output hash recorded above.
- Compile: `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/python -m compileall -q jarvis/src` — exit 0.
- Diff check: `git diff --check` — passed, exit 0.

## Strict TDD

`tasks.md` and `apply-progress.md` contain RED → GREEN → TRIANGULATE → REFACTOR evidence for this callback slice. The focused tests exist and remain GREEN. Evidence records no browser, socket, network, credentials, token exchange, API, catalog, playback, or provider activity.

## Task completion and broad OAuth boundary

The dedicated callback safe-slice row is checked. The broad OAuth row remains exactly unchecked:

- [ ] Implement OAuth Authorization Code with PKCE, protected OS-keyring-only storage, refresh single-flight, expiry/revocation/disable cleanup, callback state validation, and redaction at concrete targets `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/config.py`, and focused tests `jarvis/tests/unit/test_spotify_oauth.py`; never add plaintext fallback or expose tokens/codes/verifiers in logs, history, prompts, TTS, URLs, or errors. <!-- sdd-owner: implementation -->

The other seven implementation rows for the user authorization gate, catalog, catalog intents, playback policy, Stage 2 lifecycle/redaction, documentation/release guidance, and full Stage 2 verification also remain unchecked. Per SDD policy, unchecked implementation tasks are critical archive blockers; this report does not claim broad OAuth completion.

## Structured status and action context

Native status for `jarvis-spotify-control` was consumed from the canonical checkout: artifact store `openspec`, repo-local workspace and allowed edit root are the canonical repository, `apply: ready`, `verify: blocked` because failed verification evidence must be rerun, and `nextRecommended: apply`. The parent supplied the matching native attempt context for this verify work unit. No action-context warning was found.

## Exact blockers

1. Eight implementation-owned task rows remain unchecked, including the broad OAuth task; archive and clean overall verification are blocked.
2. Broad OAuth, catalog, playback, and release behavior were intentionally not verified or claimed in this bounded slice.

status: fail
executive_summary: The bounded loopback callback/state slice passes focused OAuth tests, the full offline suite, compileall, and diff check with no live side effects; the overall OpenSpec change remains blocked by eight unchecked implementation tasks, including the broad OAuth task.
artifacts: openspec/changes/jarvis-spotify-control/verify-report.md
next_recommended: sdd-apply
risks: Broad OAuth and later Stage 2 behavior remain incomplete; this report authorizes no live integration or provider activity.
skill_resolution: fallback-path

## Key Learnings

1. Pure callback validation can prove redirect, state, session, expiry, and one-time guarantees without network access.
2. A checked safe-slice row does not complete the broader OAuth implementation task.

## Exact remaining unchecked implementation task lines

- [ ] **User authorization gate:** before creating Spotify developer credentials, registering an application, adding OAuth configuration, or making any OAuth/API call, stop and obtain explicit user authorization for the external integration, redirect setup, approved scopes (`user-read-playback-state` and `user-modify-playback-state` only), and Premium requirement; record the decision in the change notes. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a test/guard proving Stage 2 cannot initialize when opt-in or authorization is absent; GREEN is the explicit gate state; TRIANGULATE verifies a clean environment and Stage 1 operation remain network/secret-free; REFACTOR makes the gate auditable and non-bypassable. <!-- sdd-owner: implementation -->
- [ ] Implement OAuth Authorization Code with PKCE, protected OS-keyring-only storage, refresh single-flight, expiry/revocation/disable cleanup, callback state validation, and redaction at concrete targets `jarvis/src/jarvis/services/spotify.py`, `jarvis/src/jarvis/config.py`, and focused tests `jarvis/tests/unit/test_spotify_oauth.py`; never add plaintext fallback or expose tokens/codes/verifiers in logs, history, prompts, TTS, URLs, or errors. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers absent opt-in, state mismatch, storage failure, refresh rotation, invalid grant, revoke deletion, and secret leakage; GREEN adds the minimum PKCE/keyring lifecycle; TRIANGULATE uses fake callback/API/keyring plus log/history/TTS redaction scans; REFACTOR isolates provider details and keeps Stage 1 credential-free. <!-- sdd-owner: implementation -->
- [ ] Add authorized album/artist catalog contracts and normalization at `jarvis/src/jarvis/services/spotify.py` (split catalog client if necessary) with tests in `jarvis/tests/unit/test_spotify_catalog.py`: bounded query/results, official search endpoint only, no-result/single/multiple normalization, opaque short-lived session-bound selection IDs, replacement/TTL/off/cancellation invalidation, and no playback during search or ambiguity. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported kinds, oversized queries, empty/multiple results, expired/mismatched selections, and accidental playback; GREEN implements normalized candidates and mandatory clarification; TRIANGULATE exercises fake HTTP, clock, session lifecycle, and redaction; REFACTOR discards raw provider payloads. <!-- sdd-owner: implementation -->
- [ ] Extend validated intent prompts/patterns and dispatch for `spotify_search` and `spotify_play_selection` in `jarvis/src/jarvis/interpreter/schema.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/interpreter/golden.py`, and `jarvis/src/jarvis/actions/base.py`; add tests in `jarvis/tests/unit/test_spotify_intents.py` proving numbers/exact pending references are the only clarification selectors and arbitrary URI/device/entity data cannot cross the boundary. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers unsupported playlist/recommendation/track/account requests and LLM-injected backend fields; GREEN adds constrained routing; TRIANGULATE combines deterministic Spanish forms, malformed provider-like payloads, and registry tests; REFACTOR preserves generic `execute` rejection and existing interpretation caches. <!-- sdd-owner: implementation -->
- [ ] Implement Premium/account/device readiness and playback policy in `jarvis/src/jarvis/services/spotify.py` with tests in `jarvis/tests/unit/test_spotify_playback.py`: require valid scopes and Premium, verify local Spotify identity plus exactly one configured desktop fingerprint, source URI only from current pending candidates, use bounded playback/readback, and fail closed for missing/ambiguous/unplayable/unknown targets without transfer, Connect fallback, device switching, browser automation, or MPRIS fallback. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED covers every policy gate and asserts no playback call on failure; GREEN adds one-target playback and state verification; TRIANGULATE uses fake Web API plus local identity and cancellation races; REFACTOR separates policy from transport and retains typed safe errors. <!-- sdd-owner: implementation -->
- [ ] Integrate Stage 2 status/error speech, diagnostics, history/log redaction, and lifecycle cancellation in `jarvis/src/jarvis/actions/base.py`, `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/diagnose.py`, and `jarvis/src/jarvis/orchestrator/logs.py`; add regression tests covering unauthorized, expired, revoked, storage unavailable, timeout, Premium failure, target failure, clarification, off, goodbye, stale result, TTS/microphone barriers, and unchanged destructive/open-app paths. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED demonstrates leaked/late/incorrect success paths; GREEN maps safe typed outcomes through the existing FSM; TRIANGULATE runs full offline regression plus fake API/keyring and lifecycle tests; REFACTOR centralizes redaction and preserves existing safety gates. <!-- sdd-owner: implementation -->
- [ ] Document OAuth consent, minimum scopes, Premium requirement, local-only versus networked behavior, clarification rules, target restrictions, disable/revoke procedure, and rollback in `jarvis/docs/comandos_jarvis.md` and the change notes; verify no secrets or raw catalog data appear in repository artifacts. RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is a documentation/privacy review finding missing gates or secret-like material; GREEN is complete user-facing guidance; TRIANGULATE checks docs against spec/design and redaction tests; REFACTOR removes ambiguous language and keeps Stage 1 instructions independently usable. <!-- sdd-owner: implementation -->
- [ ] Run the complete required pytest command and an explicitly authorized, bounded integration smoke test only if credentials, keyring, network, Premium account, Spotify Desktop, and the configured target are all available; record results, known limitations, and the Stage 2 rollback (disable/revoke and delete keyring material without changing Stage 1). RED → GREEN → TRIANGULATE → REFACTOR evidence: RED is the pre-release failure matrix; GREEN is deterministic suite plus authorized smoke success/failure classification; TRIANGULATE compares provider responses with policy fakes and verifies no fallback device; REFACTOR closes test isolation and release-readiness defects without adding scope. <!-- sdd-owner: implementation -->
