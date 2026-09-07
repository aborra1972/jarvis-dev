# Implementation Tasks: Slice 1 — Cancellable Onset Waiting and Fail-Closed Confirmation

This artifact plans only slice 1 and does not authorize apply. The maintainer selected chained PRs using **stacked-to-main**: each PR lands on `main`, and the next PR targets the resulting `main`.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 450–700 total across three PRs, including focused tests and implementation docs |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3, each targeting `main` successively |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

## Shared scope and rules

- Implement only cancellable indefinite ordinary onset waiting, bounded pre-onset retention, finite post-onset capture, and fail-closed dangerous confirmation with verified completion and a non-renewable 15-second authorization.
- Preserve existing wake gating, playback non-overlap, speaker verification, action allowlists, history, providers, and retention behavior.
- Use strict TDD in every PR: RED → GREEN → TRIANGULATE → REFACTOR. Tests remain with the behavior they verify.
- Verification command when apply is authorized: `jarvis/.venv/bin/pytest`; this planning phase runs no tests.
- Every PR must remain below 400 changed lines, have a clean diff containing only its boundary, and be independently revertible after its predecessor lands.

## Chain overview

```text
main
  └── 📍 PR 1: bounded cancellable capture → main
        └── PR 2: verified, non-renewable confirmation → main
              └── PR 3: loop integration, races, observability → main
```

Follow-up slices remain outside this chain: persistent conversation and explicit goodbye control (slice 2), then cancelled output and echo-safe interruption with hardware evidence (slice 3).

## PR 1 — Bounded cancellable ordinary capture

**Estimated changed lines:** 170–260, including tests. **Target:** `main`. **Start boundary:** existing `gather_utterance`/capture behavior and existing capture tests. **End boundary:** a tested capture result/mode seam that distinguishes cancellation, device failure, and utterance readiness; no confirmation or loop policy changes.

**Prior dependencies:** none. **Follow-up:** PR 2 consumes the finite confirmation capture seam; PR 3 consumes operation cancellation and result semantics. **Rollback:** revert PR 1 to restore the prior finite capture path; do not use rollback to restore late confirmation authorization.

### Dependency diagram

```text
main baseline
   └── 📍 PR 1 (capture.py, capture contracts/config, capture tests)
```

### RED

- [x] Add failing tests in `jarvis/tests/unit/test_audio_capture.py` and the narrow capture-contract test location for ordinary-mode onset waiting, repeated `None` polls, cancellation during waiting/collection, device failure, bounded pre-roll, onset-relative duration, trailing silence, and maximum utterance limits. <!-- sdd-owner: implementation -->
- [x] Add failing tests proving a finite confirmation capture mode cannot inherit ordinary indefinite onset waiting and that idle-only input produces no dispatchable utterance. <!-- sdd-owner: implementation -->

### GREEN

- [x] Implement `CaptureMode`, capture outcomes, and the smallest compatible result seam in `jarvis/src/jarvis/audio/capture.py` or its existing contract module; keep no-frame polling distinct from silence and device failure. <!-- sdd-owner: implementation -->
- [x] Implement cancellable ordinary onset waiting with a bounded deque configured independently from `AUDIO_MAX_UTTERANCE_S`, discarding the oldest idle block without retaining idle-only audio. <!-- sdd-owner: implementation -->
- [x] Preserve finite post-onset trailing-silence and maximum-duration behavior, start duration at onset, and add only narrowly scoped validated settings such as `AUDIO_PREROLL_S` and a read poll interval in `jarvis/src/jarvis/config.py`. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Run the focused capture tests and adjacent existing capture tests, using fake reads to verify long silence followed by speech, cancellation, no-frame polling, device failure, bounded retention, and post-onset limits. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Simplify capture-mode/result naming and compatibility adapters without changing the tested semantics or touching `CONVERSATION_WINDOW_S`; record the PR's clean diff and rollback point. <!-- sdd-owner: implementation -->

**Acceptance:** ordinary waiting is cancellable and does not retain unbounded idle audio; no-frame is retryable; device failure is distinct; post-onset audio remains finite; confirmation callers have an explicitly finite mode. **Observability:** expose structured capture-start, onset, cancellation, device-failure, completion, and no-frame metadata without logging retained audio. **Out of scope:** STT adaptation, authorization, loop integration, persistent conversation, goodbye parsing, barge-in/AEC, hardware, providers, retention, and backend rewrite.

## PR 2 — Verified completion and non-renewable confirmation

**Estimated changed lines:** 170–260, including tests. **Target:** `main` after PR 1 lands. **Start boundary:** PR 1 capture mode/result seam and the existing confirmation flow. **End boundary:** one fail-closed authorization lifecycle with a deadline of `T0 + 15s`, where `T0` is verified prompt completion; no new loop cancellation orchestration.

**Prior dependencies:** PR 1 must be merged to `main`. **Follow-up:** PR 3 wires loop-owned tokens, final execution checks, and off races. **Rollback:** revert PR 2 while retaining PR 1 capture safety; never re-enable acceptance of late affirmative results or deadline renewal.

### Dependency diagram

```text
main + PR 1 capture seam
   └── 📍 PR 2 (confirm.py, confirmation contracts/state seam, confirmation tests)
```

### RED

- [x] Add failing tests in `jarvis/tests/unit/test_confirm.py` for verified prompt completion as the only source of `T0`, rejecting enqueue time, unverified `flush()`, queue emptiness, elapsed sleep, and unverified playback state. <!-- sdd-owner: implementation -->
- [x] Add failing tests for exclusive expiry (`now >= T0 + 15s`), late classification, late execution, prompt/readiness failure, cancellation/invalidation, exactly-once consumption, and retry without prompt replay or deadline renewal. <!-- sdd-owner: implementation -->

### GREEN

- [x] Implement an authorization record and explicit pending/validated/aborted/expired/invalidated/consumed transitions in `jarvis/src/jarvis/orchestrator/confirm.py` with injected-clock checks and a fixed `CONFIRM_TIMEOUT_S = 15.0`. <!-- sdd-owner: implementation -->
- [x] Require a verified prompt-completion capability/result; fail closed when completion evidence is unavailable or prompt/readiness fails, and keep the existing `Speaker` protocol source-compatible where possible in `jarvis/src/jarvis/orchestrator/contracts.py`. <!-- sdd-owner: implementation -->
- [x] Keep capture/STT retry handling on the same authorization record, reject stale results before confirmation and before execution handoff, and consume authorization exactly once. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Run `jarvis/tests/unit/test_confirm.py` with fake clocks, completion outcomes, late STT, and executor gates; verify equality, late-result, invalidation, and non-renewal paths all fail closed. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Consolidate deadline and authorization invariants into narrow helpers, preserve user-visible timeout/cancel mappings, and record a clean PR 2 diff that changes no conversation lifecycle or playback policy. <!-- sdd-owner: implementation -->

**Acceptance:** no affirmative authorizes before verified completion, at equality, after expiry, after invalidation, or after a final validity failure; retries cannot renew the record. **Observability:** emit prompt-completion-verified, confirmation-expired, confirmation-invalidated, late-result, and authorization-consumed metadata with operation/reason/state/timestamps and no unnecessary affirmative content. **Out of scope:** persistent conversation, goodbye parser, barge-in/AEC, hardware, providers, retention, and general backend rewrite.

## PR 3 — Loop ownership, race integration, and regression proof

**Estimated changed lines:** 150–220, including tests and focused documentation updates. **Target:** `main` after PR 2 lands. **Start boundary:** PR 1 capture and PR 2 authorization seams. **End boundary:** loop-enforced cancellation and final authorization checks with deterministic cross-component evidence; no persistent-session behavior.

**Prior dependencies:** PRs 1 and 2 must be merged to `main`. **Follow-up:** slice 2 may consume the invalidation seam for goodbye and active conversation; slice 3 may consume operation tokens for output interruption only after separate approval and hardware evidence. **Rollback:** disable the new ordinary mode selection and revert PR 3 alone; retain PR 2 fail-closed confirmation and PR 1 bounded capture semantics.

### Dependency diagram

```text
main + PR 1 + PR 2
   └── 📍 PR 3 (loop.py, narrow contracts/state seams, loop/switch tests)
         └── later: slice 2 conversation control; slice 3 interruption hardware gate
```

### RED

- [x] Add failing tests in `jarvis/tests/unit/test_loop.py` and `jarvis/tests/unit/test_switch_signal.py` for monotonically increasing operation tokens, off/shutdown cancellation, late worker results, final execution-time authorization checks, and preservation of non-overlap behavior. <!-- sdd-owner: implementation -->
- [x] Add failing pipeline tests in `jarvis/tests/unit/test_audio_pipeline.py` proving cancelled, empty, no-frame-only, and device-failed captures create no WAV, invoke no STT, and dispatch no transcript. <!-- sdd-owner: implementation -->

### GREEN

- [x] Thread capture mode, deadline, and operation cancellation through `jarvis/src/jarvis/audio/pipeline.py` and `jarvis/src/jarvis/orchestrator/loop.py`; prevent any invalidated operation from starting capture, playback, interpretation, or execution. <!-- sdd-owner: implementation -->
- [x] Ensure GUI off has precedence, releases audio resources, invalidates authorization, and blocks late completion; expose a narrow future goodbye-invalidation seam without implementing goodbye parsing. <!-- sdd-owner: implementation -->
- [x] Check authorization immediately before entering `EXECUTING`, preserve ordinary availability after timeout/refusal/recoverable failure, and keep confirmation capture finite even while ordinary capture waits indefinitely. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Add deterministic fake-clock, fake-capture, prompt-completion, and executor-gate scenarios across `test_audio_pipeline.py`, `test_confirm.py`, `test_loop.py`, and `test_switch_signal.py`; run the focused set plus adjacent audio/orchestrator unit tests and investigate regressions. <!-- sdd-owner: implementation -->
- [x] Verify the acceptance checklist against PC-V04 and PC-S01 and record that unit evidence is not PC-V06 hardware evidence; inspect each chained PR diff remains under 400 changed lines. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Remove duplicated token/deadline plumbing, review structured log fields and `STT_ERROR_SPOKEN`/`CONFIRM_TIMEOUT_SPOKEN`/`CONFIRM_CANCEL_SPOKEN` mappings, and preserve a clean independently revertible PR 3 boundary. <!-- sdd-owner: implementation -->

**Acceptance:** off/cancellation wins races; no late capture/STT result dispatches or executes; no cancelled/empty capture reaches STT; final authorization is checked before execution; existing wake gating and non-overlap remain green. **Observability:** distinguish no-frame polls, cancellation, silence, device failure, late confirmation, and consumed authorization without transcript or idle-buffer leakage. **Out of scope:** persistent conversation, goodbye parsing implementation, barge-in/AEC, hardware validation, providers, retention, speaker enrollment, history redesign, new commands, `TAREAS.md`, and general backend rewrite.

## Explicit out-of-scope boundary for the complete chain

No persistent conversation state, active-session expiry replacement, goodbye recognition, barge-in, AEC/audio routing, queued or in-flight TTS cancellation, hardware claims, provider migration, retention expansion, speaker enrollment, history redesign, new commands, or general backend rewrite may be added to these PRs. Slice 3 remains disabled until separately authorized real-hardware verification on both integrated notebook audio and headset/microphone targets.
