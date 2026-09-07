# Proposal: Active conversation with explicit goodbye

## Intent

After a verified wake, Jarvis should remain in an active conversation across arbitrary ordinary pauses instead of returning to wake-name standby after the former follow-up window. The user can explicitly close that conversation with the exact standalone utterance `terminamos` or `hasta luego`. Jarvis acknowledges the close through both voice and text, then returns to wake-name standby.

This proposal is limited to lifecycle and deterministic control behavior. It authorizes proposal/spec/design work only; it does not authorize implementation, source changes, tests, or configuration changes.

## Scope

- Establish active conversation only after successful wake activation.
- Keep the active session open through arbitrary ordinary pauses, recoverable STT failures, unsupported input, and re-ask cycles.
- Reuse the verified PR1 ordinary capture path: bounded pre-roll, finite post-onset utterance limits, cancellation polling, and no retained idle audio growth.
- Recognize only exact standalone `terminamos` and `hasta luego` as goodbye controls.
- Acknowledge an accepted goodbye in voice and text, invalidate any pending confirmation, and return to wake-name standby.
- During dictation, give standalone control precedence while treating quoted, mentioned, negated, and content occurrences as data.
- Keep goodbye distinct from `power_off_self`, action cancellation, and playback interruption.
- Preserve GUI-off precedence: off stops capture/output, invalidates authorization, and remains stronger than active conversation or goodbye.
- Require a fresh wake after restart or GUI/on reactivation; active conversation must not resume across that boundary.
- Preserve PR1–PR3 safety, history behavior, wake gating, finite confirmation, cancellation, and no-self-trigger/non-overlap guarantees.

## Approach

Use one loop-owned active-conversation context or an equivalent documented extension of the existing orchestrator context. Replace the ordinary follow-up deadline as the session authority with an explicit active flag/state while retaining existing operation tokens and lifecycle ownership.

Each active turn should use the existing ordinary capture seam. Silence must wait for onset without becoming unbounded recording; once onset occurs, existing finite VAD and maximum-utterance limits apply. Replies and re-asks must complete the established playback-to-microphone readiness barrier before another capture begins, without relying on guessed sleeps or enabling barge-in.

Route goodbye through a narrow deterministic transcript-control seam before ordinary intent execution. The recognizer must fail closed for ambiguous, quoted, reported, negated, or non-standalone occurrences. A goodbye must invalidate the token-bound pending authorization before any late confirmation result can be consumed. Off and terminal lifecycle authorities remain checked before capture, interpretation, confirmation acceptance, and execution.

## Traceability

| Validated evidence or decision | Proposal consequence |
|---|---|
| PR1 exposes bounded `CaptureMode.ORDINARY` and separate confirmation capture | Active waiting reuses ordinary capture; confirmation remains finite and fail-closed. |
| Existing follow-up behavior is deadline-owned | Introduce explicit loop-owned active lifecycle rather than extending a timeout. |
| Re-asks need playback completion and microphone readiness | Centralize a completion/readiness barrier before each next active capture. |
| Authorization is token-bound and invalidatable | Goodbye and off invalidate pending confirmation before late results are accepted. |
| Existing off switch cancels operation and invalidates authorization | GUI off remains the stronger precedence and is not bypassed. |
| Interpreter currently lacks a goodbye control | Add deterministic routing as a narrow control seam, not an LLM-driven executor command. |
| Session history is persisted by the existing record path | Preserve history format and semantics; do not redesign retention or conversation history. |
| Parent-confirmed product decisions | Exact standalone phrases, voice+text acknowledgement, dictation control precedence, confirmation invalidation, and fresh wake on restart/on are fixed inputs to the next artifacts. |

## Acceptance criteria

- A verified wake enters active conversation, and speech after an arbitrarily long ordinary pause is accepted without another wake name.
- Ordinary idle waiting does not accumulate unbounded retained audio; captured utterances remain bounded after onset.
- Silence, recoverable STT errors, unsupported input, and re-asks keep the active session open unless an explicit lifecycle interruption occurs.
- Exact standalone `terminamos` and `hasta luego` produce coordinated voice and text acknowledgement and return to wake-name standby.
- Quoted, mentioned, negated, ambiguous, or content occurrences of those words do not close the conversation.
- In dictation, a standalone approved goodbye is a control; quoted, mentioned, negated, and content occurrences remain dictated data.
- Goodbye invalidates pending confirmation and keeps the conversation active unless a stronger off or terminal lifecycle event applies.
- GUI off wins over active conversation and goodbye, cancels capture/output, invalidates authorization, and leaves the assistant off.
- Restart or on resumes in wake-name standby and requires a fresh wake.
- `power_off_self` retains its existing golden recognition, finite confirmation, authorization, and terminal behavior.
- Existing wake gating, safety gates, history persistence/reload semantics, cancellation, and non-overlap/no-self-trigger behavior remain intact.
- Deterministic coverage is planned for long pauses, readiness races, cancellation, goodbye classification, dictation precedence, confirmation invalidation, lifecycle precedence, restart/on, and history regression; hardware, AEC, and barge-in behavior are not claimed.

## Risks and mitigations

- **Unexpected listening or privacy exposure:** do not persist active state across restart/on; retain GUI-off authority and operation cancellation.
- **Playback captured as user input:** require verified playback completion, stale-buffer handling, and microphone readiness before recapture; keep non-overlap and exclude barge-in.
- **Accidental conversation closure:** use exact standalone deterministic matching and fail closed for ambiguity, quotation, mention, and negation.
- **Late destructive authorization:** invalidate the existing authorization record on goodbye and off, while retaining final consume validation.
- **Lifecycle ownership drift:** keep active state loop-owned and preserve existing OFF/STOPPED precedence rather than creating an uncoordinated second FSM.
- **Scope expansion:** reuse current audio, interpreter, confirmation, lifecycle, and history seams instead of changing providers, hardware assumptions, or retention.

## Non-goals

- Barge-in, acoustic echo cancellation, or audio interruption during playback.
- Queued TTS cancellation or a new speech backend.
- Hardware support, provider changes, retention-policy changes, or history redesign.
- New general commands, goodbye aliases, or LLM-authorized closure.
- Rewriting the backend, replacing the existing FSM/loop wholesale, or persisting resumable active listening state.
- Changing `power_off_self`, destructive-command golden safety, wake gating in standby, or finite confirmation policy.

## Rollback

Place the active-session policy behind a narrow lifecycle decision point so it can be disabled to restore wake-gated finite follow-up behavior without reverting PR1 bounded ordinary capture or PR1–PR3 safety. If readiness or goodbye classification regresses, disable active mode and require a fresh wake while retaining GUI-off precedence, authorization invalidation, confirmation safety, history behavior, and non-overlap. Never restore renewable confirmation windows or late affirmative acceptance.

## Delivery boundary

This artifact is a proposal only. No implementation, test execution, source modification, specification, design, task, configuration, or archived-artifact change is authorized by this file.
