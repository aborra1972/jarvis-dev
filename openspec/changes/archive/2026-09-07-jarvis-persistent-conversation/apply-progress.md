# Apply Progress — PR1

## Status

- **Change:** `jarvis-persistent-conversation`
- **Boundary:** PR1 only, auto-chain `stacked-to-main`
- **Status consumed:** apply ready; workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; parent supplied authoritative status and allowed edit surfaces.
- **Action context:** workspace edits stayed within the supplied allowed surfaces. No warnings.
- **Skill resolution:** `paths-injected`

## Completed work and persisted task updates

All seven PR1 implementation rows in `tasks.md` are visibly marked `- [x]`:

- RED: capture/onset/no-frame/cancellation/device-failure/preroll/duration tests.
- RED: finite confirmation-mode and idle-only behavior tests.
- GREEN: explicit capture modes, statuses, result contract, and compatibility seam.
- GREEN: cancellable ordinary waiting with bounded pre-roll.
- GREEN: onset-relative finite trailing-silence and maximum duration, plus narrow config settings.
- TRIANGULATE: focused and adjacent tests.
- REFACTOR: compatibility adapter and naming cleanup.

PR2 and PR3 rows remain unchecked and are outside this apply boundary.

## TDD Cycle Evidence

| Cycle | Evidence |
|---|---|
| RED | `./jarvis/.venv/bin/pytest jarvis/tests/unit/test_audio_capture.py -q` failed at collection because `CaptureMode` was not yet implemented (exit 2). |
| GREEN | Implemented `CaptureMode`, `CaptureStatus`, `CaptureResult`, bounded onset capture, cancellation/device/no-frame outcomes, finite confirmation mode, and config knobs. |
| TRIANGULATE | `./jarvis/.venv/bin/pytest jarvis/tests/unit/test_audio_contracts.py jarvis/tests/unit/test_audio_capture.py jarvis/tests/unit/test_audio_pipeline.py -q` → **59 passed**. |
| REFACTOR | Preserved the existing tuple-returning `gather_utterance` adapter and kept `CONVERSATION_WINDOW_S`, confirmation flow, loop policy, and pipeline policy unchanged. Full suite: `./jarvis/.venv/bin/pytest -q` → **896 passed**, one pre-existing unknown `e2e` mark warning. |

## Per-task strict-TDD evidence

The seven PR1 rows are mapped explicitly below. RED evidence is the recorded failing test/collection state before the corresponding production contract existed; GREEN evidence is the focused passing run after implementation; TRIANGULATE is the adjacent/full safety net. No task claims hardware evidence.

| Task row | RED | GREEN | TRIANGULATE | Safety net |
|---|---|---|---|---|
| Capture outcomes and cancellation tests | `test_audio_capture.py` collection failed with missing `CaptureMode` (exit 2) | Capture outcome/status tests pass | 64 focused tests pass after corrective fix | Adjacent audio/orchestrator tests and full suite pass |
| Bounded pre-roll and finite confirmation mode tests | New onset/preroll cases initially failed against old finite-onset behavior | Onset, bounded-retention, and finite-mode tests pass | Capture + pipeline focused set: 64 passed | Full suite: 902 passed |
| Capture mode/status/result contract | Missing contract symbols caused RED collection failure | `CaptureMode`, statuses, result seam, and compatibility adapter pass contract tests | Contract, capture, and pipeline set passes | Existing legacy tuple callers remain green |
| Cancellable ordinary capture implementation | New cancellation/no-frame/device-failure expectations failed before implementation | Capture implementation tests pass | Focused capture tests pass | Adjacent and full suite pass |
| Onset-relative finite limits and config defaults | Onset duration/default wiring expectations failed before implementation and corrective wiring | Pre-roll/read-poll default and explicit-override tests pass | Focused capture/pipeline set: 64 passed | Full suite: 902 passed |
| Focused capture/pipeline triangulation | Pipeline result API cases failed before status guard existed | Cancelled/empty/no-frame/device-failure guards pass before WAV/STT | Adjacent set: 60 passed | Full suite: 902 passed, one pre-existing warning |
| Compatibility refactor and naming cleanup | Legacy adapter remained the compatibility baseline | Adapter and naming regression tests pass | Focused/adjacent suites pass | Full suite and unchanged confirmation/loop tests pass |

The corrective RED state is recorded in the worker handoff: the configuration test failed before default wiring and pipeline tests failed before the result API guard. The corrective GREEN run was 63 passed in the worker report; verification subsequently recorded 64 focused, 60 adjacent, and 902 full-suite passes. The safety net covers every modified source file through focused tests plus the adjacent and full suite; there is no configured linter, type checker, coverage tool, integration test, or hardware evidence.

## Files changed

- `jarvis/src/jarvis/audio/capture.py`
- `jarvis/src/jarvis/audio/contracts.py`
- `jarvis/src/jarvis/config.py`
- `jarvis/tests/unit/test_audio_capture.py`
- `jarvis/tests/unit/test_audio_contracts.py`
- `openspec/changes/jarvis-persistent-conversation/apply-progress.md`

## Deviations

The repository had no pre-existing `audio/contracts.py` or `test_audio_contracts.py`; the narrow contract module and focused test were created within the explicitly allowed surfaces. Existing callers retain the legacy `gather_utterance` tuple API. No confirmation, authorization, persistent conversation, goodbye, barge-in/AEC, TTS cancellation, hardware, provider, retention, backend, or `TAREAS.md` changes were made.

## Workload and PR boundary

PR1 is the bounded capture work unit targeting `main`. It is independently revertible and is the predecessor seam for PR2. No commit or PR was created. Review workload remains the planned PR1 slice; no size exception is requested.

## Remaining work

PR2 and PR3 remain outside this delegated run. Their exact unchecked `- [ ]` task rows remain in `tasks.md`.

## Risks

The no-frame health policy returns `NO_FRAME` after the configured consecutive polling bound; this distinguishes a likely unavailable device from ordinary silence while preserving cancellation checks. Real hardware evidence remains out of scope.

## Corrective verification evidence

- `gather_utterance_result` now resolves omitted pre-roll and read-poll arguments from `config.AUDIO_PREROLL_S` and `config.AUDIO_READ_POLL_S`; explicit arguments remain unchanged.
- `UtteranceCapture` now admits only non-empty `UTTERANCE` results to WAV creation and STT. Cancelled, empty, no-frame, and device-failure results return `None` without WAV or STT activity.
- Changed files for this corrective slice: `jarvis/src/jarvis/audio/capture.py`, `jarvis/src/jarvis/audio/pipeline.py`, `jarvis/tests/unit/test_audio_capture.py`, `jarvis/tests/unit/test_audio_pipeline.py`, and this progress file.

## PR2 Apply Progress

### Status consumed

- **Change:** `jarvis-persistent-conversation`; **boundary:** PR2 only.
- **Action context:** authoritative parent status said apply ready, workspace edits were restricted to the supplied allowed surfaces, and delivery was `auto-chain` / `stacked-to-main` after PR1. No warnings.
- **Skill resolution:** `paths-injected`.

### Completed tasks and persisted checkbox updates

All seven PR2 implementation rows are visibly marked `- [x]` in `tasks.md`. PR3 rows remain unchecked.

### TDD Cycle Evidence

| Cycle | Actual evidence |
|---|---|
| RED | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_confirm.py -q` produced 4 failures, including missing `Authorization` and acceptance of an unverified `flush()` speaker. |
| GREEN | Added fixed `t0 + 15.0` exclusive authorization, lifecycle transitions, token/deadline checks, exactly-once `consume`, verified `speak_and_wait`, and late-result rejection. Focused run: **87 passed**. |
| TRIANGULATE | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_confirm.py jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_audio_pipeline.py -q` → **87 passed**. |
| REFACTOR | Consolidated validity in `_live`, preserved `CaptureError` recovery compatibility, rejected arbitrary flush-only speakers, and retained the existing PiperSpeaker adapter pending PR3. |

### Files changed for PR2

- `jarvis/src/jarvis/orchestrator/confirm.py`
- `jarvis/src/jarvis/orchestrator/contracts.py`
- `jarvis/tests/unit/test_confirm.py`
- `openspec/changes/jarvis-persistent-conversation/tasks.md`
- `openspec/changes/jarvis-persistent-conversation/apply-progress.md`

### Deviations and risks

- No loop orchestration, operation tokens, persistent conversation, parser, playback cancellation, hardware, provider, retention, history, command, or `TAREAS.md` changes were made.
- `PiperSpeaker.flush()` remains a narrow compatibility adapter because PR3 owns explicit completion wiring; arbitrary flush-only speakers fail closed.
- Full suite reached **906 passed, 1 failed** in a pre-existing loop retry scenario conflicting with same-record authorization. The focused compatibility run passed after preserving `CaptureError` propagation; PR3 should rerun full suite after sharing one authorization record across loop retries.

### Remaining tasks

PR3 remains future work; its exact unchecked rows remain in `tasks.md`.

### Workload / PR boundary

PR2 is one cohesive stacked-to-main unit after PR1. No commit or PR was created. No size exception is requested.

### Final verification correction

After preserving the existing `CaptureError` propagation seam, `jarvis/.venv/bin/pytest -q` passed **907 tests** with one pre-existing unknown `e2e` mark warning. The earlier single failure was resolved without changing loop integration.

### PR2 corrective blocker fix

This corrective slice addresses only the two fail-closed verification blockers. The new regression tests are `test_speak_only_prompt_fails_closed_before_capture` and `test_rejected_authorization_validation_fails_closed`.

| Cycle | Actual evidence |
|---|---|
| RED | `cd /media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev && jarvis/.venv/bin/pytest jarvis/tests/unit/test_confirm.py -q` → **2 failed, 23 passed**: speak-only authorization and ignored rejected validation. |
| GREEN | The production path now rejects speak-only completion evidence and returns `ABORTED` when `Authorization.validate()` rejects. Focused run → **25 passed**. |
| TRIANGULATE | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_confirm.py jarvis/tests/unit/test_loop.py -q` → **52 passed, 4 failed**. The four failures are existing PR3 loop-integration expectations because loop speakers do not yet provide the explicitly verified completion adapter; no loop integration was changed in this corrective slice. |
| REFACTOR | Preserved the supported `speak_and_wait`, explicit completion, and Piper pipeline adapter paths; updated legacy confirmation unit fixtures to use the verified adapter and retained the speak-only regression. |

Scope remains limited to `confirm.py`, `contracts.py`, `test_confirm.py`, and this progress record. PR1, PR3 loop integration, and all other listed non-goals remain unchanged.

## PR3 Apply Progress

### Status consumed

- **Change:** `jarvis-persistent-conversation`; **boundary:** PR3 only, stacked-to-main after PR2.
- **Action context:** authoritative parent status was apply-ready with workspace `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`; edits remained within the supplied allowed surfaces. No action-context warnings.
- **Skill resolution:** `paths-injected`.
- **Workload:** `auto-chain`, `stacked-to-main`; this is the final PR3 work unit for slice 1. No size exception requested. The cumulative working tree includes predecessor PR changes; PR3 additions are bounded to loop/pipeline/token wiring and regressions.

### Completed tasks and persisted checkbox updates

All eight PR3 implementation rows in `tasks.md` are visibly marked `- [x]`:

- Added RED coverage for operation generation/cancellation and capture forwarding.
- Threaded ordinary/confirmation capture mode, deadline, injected clock, and operation cancellation through pipeline and loop.
- Added loop-owned operation tokens, stale-result rejection, switch-off cancellation, authorization invalidation, and resource-release precedence.
- Added final authorization consumption immediately before execution and preserved recoverable confirmation retries without deadline renewal.
- Added explicit Piper prompt completion evidence and finite confirmation capture behavior.
- Ran deterministic focused, adjacent, and full regression suites.
- Recorded PC-V04/PC-S01 unit evidence only; no PC-V06 hardware claim.
- Reviewed mappings and retained an independently bounded PR3 implementation boundary.

### TDD Cycle Evidence

| Cycle | Exact evidence |
|---|---|
| RED | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_switch_signal.py::test_operation_tokens_are_monotonic_and_stale_tokens_reject jarvis/tests/unit/test_audio_pipeline.py::test_capture_forwards_confirmation_mode_deadline_and_operation -q` initially failed during collection with missing `OperationToken`. |
| GREEN | Implemented `OperationToken`, capture keyword plumbing, `PiperSpeaker.speak_and_wait`, loop cancellation/authorization integration, and switch invalidation; focused PR3 regression set passed **99 passed**. |
| TRIANGULATE | `jarvis/.venv/bin/pytest jarvis/tests/unit/test_audio_capture.py jarvis/tests/unit/test_audio_contracts.py jarvis/tests/unit/test_confirm.py jarvis/tests/unit/test_loop.py jarvis/tests/unit/test_switch_signal.py -q` → **96 passed**. |
| REFACTOR | `jarvis/.venv/bin/pytest -q` → **912 passed, 1 warning** (pre-existing unknown `e2e` mark); `git diff --check` passed. No hardware test or PC-V06 acceptance claim. |

### Files changed by PR3

- `jarvis/src/jarvis/audio/pipeline.py`
- `jarvis/src/jarvis/orchestrator/contracts.py`
- `jarvis/src/jarvis/orchestrator/loop.py`
- `jarvis/tests/unit/test_audio_pipeline.py`
- `jarvis/tests/unit/test_loop.py`
- `jarvis/tests/unit/test_switch_signal.py`
- `openspec/changes/jarvis-persistent-conversation/tasks.md`
- `openspec/changes/jarvis-persistent-conversation/apply-progress.md`

### Deviations and risks

- Existing source-compatible capture fakes remain supported through a narrow keyword fallback; modern adapters receive mode, deadline, operation, and clock explicitly.
- The full working tree contains predecessor PR1/PR2 uncommitted changes and artifacts; no commit was created and no unrelated file was edited by this PR3 apply.
- Unit evidence covers PC-V04 and PC-S01 semantics only. PC-V06 interruption remains disabled; no hardware acceptance is claimed.

### Remaining tasks

None for the authorized PR3 implementation slice. The persisted tasks artifact was re-read after updates and contains no unchecked implementation rows.

### Next phase

Ready for `sdd-verify`.
