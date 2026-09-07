# Tasks: Loop-owned active conversation and deterministic goodbye

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 750–1,050 total; roughly 250–350 per stacked PR |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Implementation is not authorized by this artifact. The estimate includes production code and strict-TDD tests, while preserving PR1–PR3 behavior and avoiding generated, provider, hardware, or history-redesign work. Each PR is one cohesive work unit, targets `main` after its predecessor lands, and should remain below 400 changed lines where possible.

## Scope and preserved boundaries

- Base all work on the existing PR1–PR3 capture, cancellation, wake-gating, confirmation, lifecycle, history, and non-overlap contracts.
- Use existing seams in `jarvis/src/jarvis/orchestrator/loop.py`, `state.py`, `confirm.py`, `session.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `normalize.py`, `dictation.py`, `jarvis/src/jarvis/audio/capture.py`, and `pipeline.py`; inspect exact symbols before editing.
- Keep `power_off_self` separate with its golden recognition, finite 15-second confirmation, final consume check, and terminal behavior.
- Exclude barge-in/AEC, queued TTS cancellation, hardware/provider changes, retention or history redesign, new commands/aliases, LLM closure, and backend/FSM rewrite.

## Dependency diagram

```text
PR1–PR3 baseline
      |
      v
📍 PR 1: deterministic goodbye control + dictation precedence
      |
      v
📍 PR 2: loop-owned active epoch + bounded capture/readiness barrier
      |
      v
📍 PR 3: confirmation/lifecycle races + regressions, history, restart/on
      |
      v
main
```

## PR 1 — Deterministic goodbye control and dictation precedence

**Start:** PR1–PR3 interpreter and dictation behavior is unchanged. **Finish:** exact standalone `terminamos`/`hasta luego` produces a lifecycle control result, while all non-standalone and content forms remain ordinary data or re-ask input. **Dependency:** PR1–PR3 baseline only. **Follow-up:** PR2 consumes the control in the active loop. **Rollback:** revert this parser/dictation work unit without changing capture or confirmation safety. **Verification boundary:** focused interpreter, normalization, and dictation tests plus the existing interpreter/dictation suites.

### RED

- [x] Add failing unit tests in `jarvis/tests/unit/test_normalize.py` and `jarvis/tests/unit/test_interpreter.py` for exact standalone phrases, permitted case/outer-whitespace normalization, and rejection of longer, quoted, mentioned, reported, negated, ambiguous, and mixed-content transcripts. <!-- sdd-owner: implementation -->
- [x] Add failing dictation tests in `jarvis/tests/unit/test_dictation.py` proving standalone goodbye wins over content insertion, while `escribí "hasta luego" en la nota`, mentions, reports, negations, and embedded content remain dictated data. <!-- sdd-owner: implementation -->

### GREEN

- [x] Implement the narrow deterministic classifier and lifecycle-control result in `jarvis/src/jarvis/interpreter/normalize.py` and `jarvis/src/jarvis/interpreter/interpreter.py`; accept only exact normalized phrases and never invoke the LLM or executor for closure. <!-- sdd-owner: implementation -->
- [x] Route the standalone control before `DictationManager.process_transcript` in `jarvis/src/jarvis/interpreter/dictation.py`, preserving existing `enviar`, exit, and clear controls and existing transcript data behavior. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Run the focused PR1 tests and `jarvis/.venv/bin/pytest jarvis/tests/unit/test_interpreter.py jarvis/tests/unit/test_normalize.py jarvis/tests/unit/test_dictation.py`; verify no ordinary or destructive intent is emitted for rejected forms. <!-- sdd-owner: implementation -->
- [x] Run the existing golden, NLU, and session-facing tests under `jarvis/tests/unit/` to confirm parser changes do not alter command aliases, `power_off_self`, or persisted turn semantics. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Centralize exact phrase constants and boundary normalization without adding aliases, fuzzy matching, quotation parsing that broadens acceptance, or new command abstractions; rerun the PR1 suite. <!-- sdd-owner: implementation -->

### PR 1 acceptance and observability

- Exact standalone controls are deterministic lifecycle results; every other goodbye-like surface fails closed and remains available to ordinary handling/data.
- Emit compatible structured `goodbye.accepted(source=voice|dictation)` and `goodbye.rejected(reason=nonstandalone|ambiguous)` events without raw audio or transcript-retention changes.

## PR 2 — Active epoch, arbitrary pauses, and playback-to-mic barrier

**Start:** PR1 is landed and its classifier contract is available. **Finish:** a verified wake owns an active epoch across arbitrary ordinary pauses, recoverable outcomes, and re-asks; every recapture passes verified speech completion, stale-buffer flush, and microphone readiness. **Dependency:** PR1. **Follow-up:** PR3 adds confirmation invalidation and final lifecycle regression coverage. **Rollback:** disable the active decision point to restore finite follow-up/wake-gated behavior while retaining PR1 and PR1–PR3 safety. **Verification boundary:** loop/audio tests and the full pre-PR3 suite; no hardware claim.

### RED

- [x] Add failing loop tests in `jarvis/tests/unit/test_loop.py` for verified-wake activation, ordinary speech after an arbitrarily long pause, silence, `NO_FRAME`, recoverable STT failure, unsupported input, unresolved input, re-ask persistence, cancellation, and fresh wake gating after restart/on. <!-- sdd-owner: implementation -->
- [x] Add failing audio/playback tests in `jarvis/tests/unit/test_audio_capture.py`, `test_audio_pipeline.py`, and `test_audio_playback.py` proving no capture during TTS, explicit completion before recapture, stale-buffer flush, mic-ready verification, bounded post-onset audio, and prompt/readiness failure fail-closed. <!-- sdd-owner: implementation -->

### GREEN

- [x] Extend the single owner in `jarvis/src/jarvis/orchestrator/loop.py` with an explicit active conversation context/epoch and lifecycle checks; keep standby wake-gated, use `CaptureMode.ORDINARY`, retain operation-token cancellation, and do not make `CONVERSATION_WINDOW_S` the active authority. <!-- sdd-owner: implementation -->
- [x] Implement one injected completion/readiness barrier using `jarvis/src/jarvis/audio/pipeline.py` and existing `jarvis/src/jarvis/audio/capture.py` bounded flush/readiness seams; keep confirmation capture separate and finite and leave `BARGE_IN_ENABLED=False`. <!-- sdd-owner: implementation -->
- [x] Preserve GUI off and terminal precedence in `jarvis/src/jarvis/orchestrator/state.py` and `loop.py`: cancel capture/output, clear active state, and prevent stale results or playback completion from reactivating conversation. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Run focused loop/audio tests and `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_audio_capture.py jarvis/tests/unit/test_audio_pipeline.py jarvis/tests/unit/test_audio_playback.py`; inspect operation/epoch traces for stale drops and no overlap. <!-- sdd-owner: implementation -->
- [x] Run the full existing suite with `jarvis/.venv/bin/pytest`; verify PR1–PR3 wake gating, cancellation, non-overlap/no-self-trigger, history, and destructive golden behavior remain green. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Centralize barrier and precedence checks, retain compatibility configuration only for rollback, and remove deadline-based active authority without rewriting the backend or introducing resumable active state. <!-- sdd-owner: implementation -->

### PR 2 acceptance and observability

- Active ordinary capture survives arbitrary pauses and recoverable outcomes, but never accumulates unbounded idle audio or captures TTS/stale buffered audio.
- Log `conversation.activated(epoch)`, `turn.waiting`, `barrier.ready/failed`, `stale_result_dropped(epoch)`, and `off_precedence` at the documented levels without raw audio.

## PR 3 — Goodbye close, confirmation invalidation, and lifecycle regressions

**Start:** PR2 is landed with active epochs and the barrier. **Finish:** accepted goodbye acknowledges through voice and text, closes only the active conversation, invalidates pending confirmation safely, and all lifecycle/history regressions are covered. **Dependency:** PR2. **Follow-up:** normal verification and rollout observation only. **Rollback:** revert the close/invalidation integration to PR2 active behavior; never restore renewable confirmation or accept late affirmatives. **Verification boundary:** focused confirmation/lifecycle/history tests followed by the complete configured suite.

### RED

- [x] Add failing integration-style unit tests in `jarvis/tests/unit/test_loop.py` and `jarvis/tests/unit/test_confirm.py` for goodbye voice+text acknowledgement, standby return while powered on, goodbye during confirmation capture, late affirmative rejection by token/epoch, and active listening after invalidation. <!-- sdd-owner: implementation -->
- [x] Add failing regression tests in `jarvis/tests/unit/test_switch_signal.py`, `test_state.py`, `test_session.py`, `test_actions_lifecycle.py`, and relevant `test_golden.py` coverage for off-wins/no acknowledgement, restart/on fresh wake, history preservation/reload, cancellation, `power_off_self` separation, and existing finite confirmation. <!-- sdd-owner: implementation -->

### GREEN

- [x] Integrate the PR1 lifecycle control into `jarvis/src/jarvis/orchestrator/loop.py` so exact goodbye closes from active waiting/processing, emits the configured voice and text acknowledgement, invalidates the active epoch, and returns to wake-name standby without powering off. <!-- sdd-owner: implementation -->
- [x] In `jarvis/src/jarvis/orchestrator/confirm.py` and the loop boundary, atomically invalidate pending authorization with reason `goodbye` before any late verdict can be consumed; retain final token, deadline, cancellation, and off checks. <!-- sdd-owner: implementation -->
- [x] Preserve `jarvis/src/jarvis/orchestrator/session.py` record/save/reload format and lifecycle history semantics; do not add retention or history-model changes. <!-- sdd-owner: implementation -->

### TRIANGULATE

- [x] Run focused PR3 tests with `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_confirm.py jarvis/tests/unit/test_switch_signal.py jarvis/tests/unit/test_state.py jarvis/tests/unit/test_session.py jarvis/tests/unit/test_golden.py`; verify off suppresses both acknowledgement channels and no destructive action executes after goodbye. <!-- sdd-owner: implementation -->
- [x] Run `jarvis/.venv/bin/pytest` and review the diff/stat for each stacked PR, confirming each remains under 400 changed lines where possible and no excluded surface or generated artifact changed. <!-- sdd-owner: implementation -->

### REFACTOR

- [x] Simplify lifecycle precedence and acknowledgement dispatch around one epoch owner, document stale-result cleanup, and rerun focused plus full tests without changing GUI state strings, history persistence, or `power_off_self`. <!-- sdd-owner: implementation -->

### PR 3 acceptance and observability

- Exact goodbye produces coordinated voice/text acknowledgement, invalidates confirmation, preserves powered-on standby, and requires a fresh wake after restart/on.
- Off, shutdown, cancellation, stale epochs, playback completion, and late confirmations cannot produce acknowledgement, command execution, or active-state resurrection after the stronger event.

## Cross-PR acceptance checklist

- [x] Verify all requirements and scenarios in `openspec/changes/jarvis-active-conversation-goodbye/specs/assistant-lifecycle/spec.md`, `command-interpreter/spec.md`, `voice-pipeline/spec.md`, and `system-control/spec.md` map to a test and implementation boundary. <!-- sdd-owner: implementation -->
- [x] Verify strict order RED → GREEN → TRIANGULATE → REFACTOR for every PR, using `jarvis/.venv/bin/pytest` as the configured runner and recording failures/fixes in the implementation receipts. <!-- sdd-owner: implementation -->
- [x] Verify no implementation begins until the parent/orchestrator obtains the required apply approval; this task artifact does not authorize implementation. <!-- sdd-owner: implementation -->

## Delivery and rollback

Delivery is `ask-on-risk`: implementation must pause for the review-budget decision before apply. Once approved, land the three cohesive work units as stacked PRs to `main` in order; do not merge a child before its dependency. Each PR carries its own start/end state, verification, rollback, and `📍` dependency diagram. If a slice exceeds 400 changed lines, stop and request a size exception rather than compressing code/tests or mixing chain strategies. Roll back the affected PR only; retain landed predecessor safety behavior. No hardware, AEC, barge-in, queued-TTS, provider, retention, history-redesign, new-command, alias, LLM-closure, or backend-rewrite acceptance is implied.
