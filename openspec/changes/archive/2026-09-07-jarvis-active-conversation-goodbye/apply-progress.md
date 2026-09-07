# Apply Progress: PR1

## Status

- `applyState`: PR1 complete; PR2 and PR3 remain unchecked.
- `actionContext`: workspace implementation; edits stayed within canonical workspace and allowed PR1 surfaces.
- Delivery boundary: PR1 only, stacked-to-main; parent authorization resolved the ask-on-risk workload gate.
- `skill_resolution`: paths-injected (requested chained-pr skill path was unavailable; work-unit guidance was loaded).

## Completed tasks and persisted checkboxes

PR1 RED, GREEN, TRIANGULATE, and REFACTOR implementation rows are marked `- [x]` in `tasks.md`. PR2, PR3, and cross-PR rows are unchanged.

## TDD Cycle Evidence

| Stage | Evidence |
|---|---|
| RED | Focused tests initially failed because `normalize_boundary` was missing; standalone dictation goodbye initially returned `(False, '')`. |
| GREEN | Implemented exact `terminamos`/`hasta luego` control, boundary normalization, and dictation precedence; focused tests passed. |
| TRIANGULATE | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_normalize.py jarvis/tests/unit/test_interpreter.py jarvis/tests/unit/test_dictation.py` — 77 passed. `jarvis/.venv/bin/pytest jarvis/tests/unit/` — 835 passed. |
| REFACTOR | Centralized `GOODBYE_PHRASES`, `is_goodbye`, and `normalize_boundary`; reran focused and full unit suites successfully. |

## Files changed by this PR1 apply

- `jarvis/src/jarvis/interpreter/normalize.py`
- `jarvis/src/jarvis/interpreter/interpreter.py`
- `jarvis/src/jarvis/interpreter/dictation.py`
- `jarvis/tests/unit/test_normalize.py`
- `jarvis/tests/unit/test_interpreter.py`
- `jarvis/tests/unit/test_dictation.py`
- `openspec/changes/jarvis-active-conversation-goodbye/tasks.md`
- `openspec/changes/jarvis-active-conversation-goodbye/apply-progress.md`

## Scope and deviations

No active loop, readiness barrier, confirmation invalidation, restart/on, history, audio, hardware, provider, retention, new aliases, LLM closure, backend rewrite, or archived change was modified. Quoted, mentioned, reported, negated, and mixed-content forms remain ordinary dictation/interpreter data paths.

## Remaining tasks

PR2 and PR3 task rows remain unchecked.

## Next recommendation

`sdd-verify` for the PR1 slice.

## PR2 Apply Progress

### Status

- `applyState`: PR2 complete; PR3 and cross-PR implementation rows remain unchecked.
- `actionContext`: workspace implementation; canonical workspace and allowed PR2 surfaces used. Existing unrelated working-tree changes were preserved.
- Delivery boundary: PR2 only, stacked-to-main; ask-on-risk decision was resolved by the parent authorization.
- `skill_resolution`: paths-injected.

### Completed tasks and persisted checkbox updates

- PR2 RED, GREEN, TRIANGULATE, and REFACTOR rows are marked `- [x]` in `tasks.md`.
- PR3 and cross-PR rows were not changed.

### TDD Cycle Evidence

| Stage | Evidence |
|---|---|
| RED | Focused loop activation test initially failed because the second ordinary turn was wake-gated; the prompt-failure test initially reported completion true. |
| GREEN | Added loop-owned `active_epoch`, ordinary recapture barrier, off clearing, and explicit Piper prompt completion failure evidence; focused tests passed. |
| TRIANGULATE | Focused loop/audio/switch command — 111 passed. |
| REFACTOR | Centralized `_prepare_ordinary_capture`, retained bounded capture and confirmation seams, and full `jarvis/.venv/bin/pytest` — 922 passed, 1 existing unknown-mark warning. |

### Files changed by PR2 apply

- `jarvis/src/jarvis/orchestrator/loop.py`
- `jarvis/src/jarvis/audio/pipeline.py`
- `jarvis/tests/unit/test_loop.py`
- `jarvis/tests/unit/test_audio_pipeline.py`
- `openspec/changes/jarvis-active-conversation-goodbye/tasks.md`
- `openspec/changes/jarvis-active-conversation-goodbye/apply-progress.md`

### Implementation boundary and deviations

The loop creates a monotonically numbered active epoch only after verified wake, uses ordinary capture without `CONVERSATION_WINDOW_S` as authority, preserves the epoch through silence/re-asks/recoverable outcomes, flushes stale buffers, checks playback completion, and verifies mic start before recapture. Off clears active state before later results can reactivate it. Standby remains wake-gated, confirmation remains separate, and PR1 goodbye classification is preserved without PR3 acknowledgement/close integration.

No changes were made to `state.py`, confirmation invalidation, history/restart redesign, barge-in/AEC, queued TTS cancellation, hardware/providers, README, TAREAS, archived changes, voice configuration, or excluded backend surfaces.

### Remaining tasks

PR3 remains the next implementation slice. Exact unchecked implementation row:

- [ ] Add failing integration-style unit tests in `jarvis/tests/unit/test_loop.py` and `jarvis/tests/unit/test_confirm.py` for goodbye voice+text acknowledgement, standby return while powered on, goodbye during confirmation capture, late affirmative rejection by token/epoch, and active listening after invalidation. <!-- sdd-owner: implementation -->

### Next recommendation

`sdd-verify`

## PR3 Apply Progress

### Status

- `applyState`: PR3 implementation tasks complete; cross-PR acceptance rows remain unchecked.
- `actionContext`: repo-local implementation in the canonical workspace; only the authorized PR3 source/test/artifact surfaces were edited. Existing unrelated working-tree changes were preserved.
- Delivery boundary: PR3 only, stacked-to-main after PR2; parent authorization resolved the ask-on-risk/high-workload gate.
- `skill_resolution`: paths-injected.

### Completed tasks and persisted checkbox updates

- PR3 RED, GREEN, TRIANGULATE, and REFACTOR rows are marked `- [x]` in `tasks.md`.
- PR1 and PR2 rows remain unchanged; cross-PR acceptance rows remain unchecked.
- The persisted task artifact was re-read after updating and confirms all PR3 implementation rows are checked.

### TDD Cycle Evidence

| Stage | Evidence |
|---|---|
| RED | Added loop and confirmation tests first. The confirmation test initially hung because goodbye had no confirmation verdict, and the loop test initially returned `silence`; both failures were observed before the implementation was complete. |
| GREEN | Added `Confirmation.GOODBYE`, atomic `Authorization.invalidate("goodbye")`, loop-owned close/acknowledgement, dictation control routing, standby return, and FSM text detail. Focused new tests passed: 2 passed. |
| TRIANGULATE | Focused PR3 command `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_confirm.py jarvis/tests/unit/test_switch_signal.py jarvis/tests/unit/test_state.py jarvis/tests/unit/test_session.py jarvis/tests/unit/test_golden.py` — 299 passed. Full `jarvis/.venv/bin/pytest` — 925 passed, 1 pre-existing unknown-mark warning. `git diff --check` passed. |
| REFACTOR | Centralized goodbye cleanup in `_close_goodbye`, retained off checks before acknowledgement, preserved operation/token invalidation and existing session/history paths, then reran focused and full suites successfully. |

### Files changed by PR3

- `jarvis/src/jarvis/orchestrator/loop.py`
- `jarvis/src/jarvis/orchestrator/confirm.py`
- `jarvis/tests/unit/test_loop.py`
- `jarvis/tests/unit/test_confirm.py`
- `openspec/changes/jarvis-active-conversation-goodbye/tasks.md`
- `openspec/changes/jarvis-active-conversation-goodbye/apply-progress.md`

### Implementation boundary and deviations

Exact standalone goodbye controls now close active conversation without invoking an executor, emit voice acknowledgement plus the GUI FSM text detail, clear active epoch and conversation-window compatibility state, and leave powered-on standby wake-gated. Confirmation capture recognizes goodbye before verdict classification, invalidates the authorization with reason `goodbye`, and rejects late token/epoch handoff. Off remains checked before closure acknowledgement. No session format, history retention, power-off action, audio backend, provider, README, TAREAS, archive, alias, or backend/FSM redesign was changed.

### Remaining tasks

Cross-PR acceptance rows remain unchecked because they are verification/delivery follow-up work outside this PR3 apply slice.

### Next recommendation

`sdd-verify`
