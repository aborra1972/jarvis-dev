# Apply Progress: jarvis-voice-turn-taking-investigation

## Structured status consumed

- Target repository/workspace: `/home/ale/Proyectos/jarvis-dev` (canonical git root `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`).
- Change: `jarvis-voice-turn-taking-investigation`.
- Artifact store: OpenSpec.
- Parent/user authorization: Slice 1, Slice 2, and Slice 3 implementation explicitly authorized; stacked-to-main delivery selected.
- Action context for Slice 3: allowed edit surfaces were limited to `jarvis/src/jarvis/orchestrator/loop.py`, `jarvis/src/jarvis/orchestrator/contracts.py`, `jarvis/src/jarvis/interpreter/interpreter.py`, `jarvis/src/jarvis/interpreter/dictation.py`, `jarvis/src/jarvis/orchestrator/logs.py`, `jarvis/tests/unit/test_loop.py`, `jarvis/tests/unit/test_interpreter.py`, `jarvis/tests/unit/test_dictation.py`, `jarvis/tests/unit/test_logs.py`, plus Slice 3 bookkeeping in this file and `tasks.md`.
- Strict TDD: active via `openspec/config.yaml` and user instruction.

## Workload / PR boundary

Slice 3 only: active lifecycle hardening, exact goodbye coverage, GUI-off interrupt precedence, stale-token/history suppression, fresh-wake boundaries, and enabled barge-in routing through readiness. No Spotify, provider/network, hardware/AEC, persistence schema, or broad backend rewrite changes were made.

Slice 3 writer-added source/test delta: `jarvis/src/jarvis/orchestrator/loop.py` plus loop/interpreter/dictation tests. The stacked worktree still includes prior Slice 1+2 diffs and unrelated pre-existing files, so HEAD-relative diff stats include more than Slice 3.

## Completed implementation evidence

- GUI off now cancels the active operation and pending authorization, then calls `speaker.interrupt()` instead of `speaker.close()`, preventing queued or active output from being flushed during off.
- Goodbye closure invalidation is test-proven for pending authorization and operation token cancellation, voice acknowledgement, standby return, and fresh-wake requirement.
- Late interpretation results whose operation token was cancelled before dispatch now fail closed before fallback notification, transcript logging, session routing, execution, TTS, follow-up, or successful history writes.
- Enabled barge-in now interrupts active/queued speech, replaces the operation token, and enters listening only through the existing `_prepare_capture()` readiness barrier.
- Interpreter and dictation tests now cover both exact standalone `terminamos` and `hasta luego`, plus non-standalone quoted/embedded/negated/reported content.

## Files changed in Slice 3

- `jarvis/src/jarvis/orchestrator/loop.py`
- `jarvis/tests/unit/test_loop.py`
- `jarvis/tests/unit/test_interpreter.py`
- `jarvis/tests/unit/test_dictation.py`
- `openspec/changes/jarvis-voice-turn-taking-investigation/apply-progress.md`
- `openspec/changes/jarvis-voice-turn-taking-investigation/tasks.md`

## TDD Cycle Evidence

| Task | Test File | Layer | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|-----|-------|-------------|----------|
| Slice 3 lifecycle/off/stale/barge-in | `jarvis/tests/unit/test_loop.py` | Unit | ✅ New tests initially failed: stale post-interpretation dispatch and barge-in readiness exposed behavior failures; off/goodbye invalidation tests first needed assertion-shape correction from nonexistent `auth.valid` to `auth.state` | ✅ Corrected focused new loop tests passed after loop changes: `4 passed` | ✅ Focused lifecycle/interpreter/dictation/log suite passed: `139 passed`; full suite passed: `1178 passed, 3 deselected` | ✅ Kept changes inside existing loop readiness/operation seams; no new public contracts, config, persistence schema, providers, hardware, or Spotify changes |
| Slice 3 exact goodbye content boundaries | `jarvis/tests/unit/test_interpreter.py`, `jarvis/tests/unit/test_dictation.py` | Unit | Covered by existing exact-goodbye tests and added boundary parametrization; production already satisfied the pure interpreter/dictation contract | ✅ Included in focused suite: `139 passed` | ✅ Both exact phrases and non-standalone content variants covered | No production refactor needed |

## Test commands run

- `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py::test_switch_off_interrupts_without_flushing_goodbye_ack jarvis/tests/unit/test_loop.py::test_goodbye_invalidates_authorization_operation_and_requires_fresh_wake jarvis/tests/unit/test_loop.py::test_stale_operation_after_interpretation_does_not_execute_or_record_history jarvis/tests/unit/test_loop.py::test_enabled_barge_in_interrupts_and_enters_listening_through_readiness_barrier` — RED before implementation: `4 failed`; two failures were behavior failures (stale dispatch and barge-in readiness), and two exposed a test assertion-shape mistake corrected before final GREEN.
- `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py::test_switch_off_interrupts_without_flushing_goodbye_ack jarvis/tests/unit/test_loop.py::test_goodbye_invalidates_authorization_operation_and_requires_fresh_wake jarvis/tests/unit/test_loop.py::test_stale_operation_after_interpretation_does_not_execute_or_record_history jarvis/tests/unit/test_loop.py::test_enabled_barge_in_interrupts_and_enters_listening_through_readiness_barrier` — GREEN after implementation: `4 passed`.
- `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py` — targeted lifecycle loop suite: `53 passed`.
- `jarvis/.venv/bin/pytest jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_interpreter.py jarvis/tests/unit/test_dictation.py jarvis/tests/unit/test_logs.py` — focused lifecycle/interpreter/dictation/log suite: `139 passed`.
- `jarvis/.venv/bin/pytest` — full stacked suite: `1178 passed, 3 deselected`.
- `git diff --check` — passed with no output.

## Deviations from design

- `contracts.py`, `interpreter.py`, `dictation.py`, and `logs.py` did not need production changes; the existing exact-goodbye and history seams were preserved and expanded through tests.
- Barge-in integration stayed entirely in `loop.py`; `BARGE_IN_ENABLED` remains disabled by default and no AEC/provider/hardware changes were added.
- `test_audio_pipeline.py` was not edited because it was outside the explicitly allowed Slice 3 edit surfaces; existing full-suite audio pipeline coverage remained green.

## Remaining tasks

- Final native review/PR preparation remains with the parent orchestrator.
- No commits or pushes were made.

## Key Learnings

- The off path was still using `close()`, which can flush queued speech; Slice 3 changed it to the existing interruption seam so off has stronger precedence than output and goodbye acknowledgement.
- The stale-token risk existed after interpretation but before session routing/logging; the new guard prevents cancelled late interpretation results from producing history, TTS, follow-up, or execution.
- The barge-in path already interrupted TTS, but bypassed capture-buffer flush and mic-readiness evidence; routing it through `_prepare_capture()` reuses the Slice 2 barrier without enabling barge-in by default.

## GUI teardown hardening follow-up

- `jarvis_gui.py` now tracks GUI-owned GLib timeout/idle source IDs and removes them during `destroy` before subprocess shutdown.
- Destroy marks the GUI closed before cleanup, so late UI refreshes, log writes, status updates, FSM polling, restart callbacks, and process-exit callbacks fail closed without touching GTK widgets.
- Subprocess cleanup still terminates the direct Jarvis process group and verified PID-file process group; closed GUI cleanup skips only widget/log updates.
- Regression coverage lives in `jarvis/tests/test_jarvis_gui.py` for source tracking/removal, closed-callback no-ops, and safe closed-window process cleanup.
