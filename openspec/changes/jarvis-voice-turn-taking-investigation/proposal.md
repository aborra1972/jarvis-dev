# Proposal: Jarvis Voice Turn-Taking Improvement

## Status

- Change: `jarvis-voice-turn-taking-investigation`
- Artifact type: OpenSpec proposal only
- Implementation authorization: not granted by this proposal
- Product scope: approved broad voice turn-taking slice
- Research note: prior research findings may be stale and must be reconciled against current code during design and implementation planning.

## Intent

Improve Jarvis voice turn-taking so spoken interactions feel reliably conversational: Jarvis should listen only when ready, avoid capturing its own speech, preserve follow-up time after actual playback, and close/restart conversations through explicit lifecycle rules.

The change addresses known local timing risks in capture, TTS playback, follow-up windows, confirmation/reask flows, and optional barge-in behavior while preserving existing safety and authorization boundaries.

## Product outcome

After the change, a user should be able to wake Jarvis, pause briefly before speaking, hear prompts fully before being recorded, continue a conversation after Jarvis finishes speaking, interrupt speech when barge-in is enabled, and explicitly end the conversation with `terminamos` or `hasta luego` without stale work carrying forward.

## Scope

In scope:

1. Initial silence boundary and timeout distinct from trailing silence.
2. One reusable readiness barrier before capture that ensures:
   - TTS playback has completed;
   - any post-playback cooldown has elapsed;
   - wake/capture buffers have been flushed;
   - microphone capture is ready before listening starts.
3. Follow-up conversation window anchored after actual playback completion, not merely command execution or TTS enqueue.
4. Barge-in behavior, where existing barge-in is enabled, that clears active playback and queued TTS.
5. Explicit active conversation lifecycle:
   - exact standalone `terminamos` closes the active conversation;
   - exact standalone `hasta luego` closes the active conversation;
   - closure includes text and voice acknowledgement;
   - closure invalidates stale work and pending confirmations;
   - GUI-off precedence remains intact;
   - a fresh wake is required after close/restart.
6. Tests and design reconciliation against current code before implementation.
7. Reviewable stacked delivery across three slices.

## Non-goals

This proposal does not include:

1. Acoustic echo cancellation (AEC).
2. Hardware, microphone, speaker, provider, or persistence redesign.
3. Changes to existing safety gates, dictation behavior, destructive authorization, `power_off_self`, or history shape.
4. Broad conversation memory redesign beyond explicit lifecycle invalidation described above.
5. Replacement of the current local batch voice architecture with a streaming protocol.
6. Any implementation work, task creation, or source/test edits as part of this proposal artifact.

## Requirements

1. Jarvis MUST distinguish initial silence before first detected speech from trailing silence after speech has started.
2. Jarvis MUST allow an initial-silence timeout long enough for a normal post-wake pause, independent from trailing-silence cutoff.
3. Jarvis MUST NOT begin capture until the readiness barrier confirms TTS completion, cooldown completion, wake-buffer flush, capture-buffer flush, and microphone readiness.
4. Confirmation and reask flows MUST use the same readiness barrier before listening for the user's response.
5. Follow-up windows MUST be calculated from actual playback completion for the user-visible response that opens the follow-up opportunity.
6. If barge-in is enabled, barge-in MUST stop active TTS and clear queued pending TTS so interrupted stale speech cannot resume.
7. Exact standalone `terminamos` and `hasta luego` utterances MUST close the active conversation.
8. Conversation closure MUST acknowledge by text and voice.
9. Conversation closure MUST invalidate pending confirmations and stale work associated with the prior active conversation.
10. GUI-off precedence MUST be preserved if an utterance could otherwise be interpreted as conversation lifecycle control.
11. After conversation closure or restart, Jarvis MUST require a fresh wake before accepting further conversation input.
12. Existing safety, dictation, destructive authorization, `power_off_self`, and history-shape guarantees MUST remain unchanged.
13. Design and implementation planning MUST reconcile research findings against the current codebase because the research snapshot may be stale.

## Affected areas

Expected affected areas during later design/implementation include:

- Audio capture boundaries and timeout handling.
- TTS speaker queue/playback state and interruption semantics.
- Orchestrator listening, confirmation, reask, speaking, cooldown, and follow-up transitions.
- Conversation lifecycle state and stale-work/confirmation invalidation.
- Tests around capture timing, speaker readiness, follow-up timing, barge-in, and lifecycle closure.

## Risks

1. Timing regressions may make Jarvis feel slower if the readiness barrier over-waits.
2. Timeout changes may accidentally make quiet users time out too early or keep the mic open too long.
3. Queue-clearing for barge-in may discard speech that should still be heard if cancellation boundaries are unclear.
4. Lifecycle closure could conflict with command interpretation if exact-standalone matching is not strict.
5. Current code may have diverged from the research snapshot, so assumptions must be revalidated before design and implementation.

## Rollout and rollback

Rollout should proceed through stacked, reviewable slices with tests proving each behavior before implementation changes are accepted.

Rollback strategy:

1. Each slice should be independently revertible.
2. If capture boundary changes regress recognition, revert the capture slice while preserving unrelated later work only if it remains test-safe.
3. If the readiness barrier causes latency or deadlock, revert barrier integration paths and restore prior capture sequencing.
4. If lifecycle closure creates command-routing regressions, revert lifecycle routing while preserving lower-level capture/TTS fixes where safe.
5. No data migration rollback is expected because the proposal does not introduce persistence redesign.

## Acceptance criteria

The change is acceptable when:

1. Tests show initial silence before first speech does not trigger trailing-silence completion.
2. Tests show capture starts only after TTS playback completion, cooldown, buffer flush, and mic readiness.
3. Confirmation and reask tests prove Jarvis does not listen while its own prompt is still active or queued.
4. Follow-up tests prove the follow-up window begins after actual playback completion.
5. Barge-in tests prove active and queued TTS are cleared when barge-in is enabled.
6. Lifecycle tests prove exact standalone `terminamos` and `hasta luego` close the active conversation with text and voice acknowledgement.
7. Lifecycle tests prove stale work and pending confirmations are invalidated after closure.
8. Tests prove GUI-off precedence and existing safety/destructive authorization behavior remain unchanged.
9. A manual or instrumented verification confirms no obvious voice turn-taking regression in the wake → listen → speak → follow-up path.
10. The implementation remains within the approved product scope or pauses for a new product decision if scope expansion is needed.

## Reviewable three-slice stacked delivery plan

Use stacked delivery to keep review focused within the repo-local 800-line review budget. Each slice should have its own tests and be reviewable independently.

### Slice 1 — Capture boundaries and readiness primitive

Purpose: establish reliable listening start conditions.

Scope:

- Split initial silence from trailing silence in capture behavior.
- Add or expose a reusable readiness barrier primitive for speak-then-listen sequencing.
- Add tests for initial-silence timeout, trailing-silence timeout, TTS completion, cooldown, wake-buffer flush, capture-buffer flush, and mic readiness.

Review boundary:

- No conversation lifecycle behavior beyond what is required to prove safe capture start.
- No barge-in queue-clearing unless needed as a narrow dependency.

### Slice 2 — Orchestrator turn sequencing and follow-up timing

Purpose: route user-visible turn transitions through the readiness model.

Scope:

- Integrate the readiness barrier into confirmation and reask paths.
- Anchor follow-up windows after actual playback completion.
- Reconcile current orchestrator behavior against stale research assumptions.
- Add tests for confirmation, reask, long TTS follow-up timing, and no capture during active/queued TTS.

Review boundary:

- Preserve existing safety, dictation, destructive authorization, `power_off_self`, and history shape.
- Do not introduce broader conversation lifecycle closure in this slice except where needed to avoid regressions.

### Slice 3 — Barge-in cancellation and explicit conversation lifecycle

Purpose: complete the approved broad product behavior.

Scope:

- When barge-in is enabled, clear active and queued TTS on interruption.
- Implement exact standalone `terminamos` and `hasta luego` conversation closure.
- Add text and voice acknowledgement for closure.
- Invalidate stale work and pending confirmations on closure.
- Preserve GUI-off precedence.
- Require fresh wake after close/restart.
- Add regression tests covering lifecycle, stale-state invalidation, GUI-off precedence, and barge-in queue clearing.

Review boundary:

- No persistence redesign, provider redesign, AEC, hardware changes, or broad memory redesign.
- Any ambiguity in lifecycle routing should pause for product/design clarification before implementation expands scope.
