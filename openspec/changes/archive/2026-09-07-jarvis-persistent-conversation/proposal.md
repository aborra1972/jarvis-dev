# Proposal: Persistent conversation with safe interruption

## Intent

Let Jarvis users activate once, take as long as needed to begin speaking, and continue across long pauses until explicitly ending the conversation. Remove timing-driven dropped turns without weakening dangerous-action authorization, the GUI off control, or protection against assistant self-triggering. Eventually, speaking over the assistant must stop its voice and preserve the user's new speech on both integrated notebook audio and a headset with microphone.

**Status: drafted for review, not approved for implementation.** The orchestrator's confirmed product handoff and Engram `sdd/jarvis-persistent-conversation/preproposal` (observation 1620) supersede the pending interview in [exploration.md](exploration.md). Product discovery is complete for this proposal; no new interview or additional consent is inferred. Research was not selected.

## Current gap and evidence

Source findings below come from the repository exploration, not runtime or hardware measurements.

| Evidence (repository-relative) | Gap |
| --- | --- |
| `jarvis/src/jarvis/audio/capture.py`; `jarvis/src/jarvis/config.py` | Initial silence counts toward endpoint/duration limits. Raising a 5/8-second timeout would not provide indefinite first-speech waiting. |
| `jarvis/src/jarvis/orchestrator/loop.py` | One-shot follow-up timing can expire during queued speech/cooldown; silence consumes the follow-up opportunity. Re-asks lack explicit playback-completion/mic-reopen coordination. |
| `jarvis/src/jarvis/orchestrator/confirm.py` | Deadline checks follow blocking capture and affirmative classification; capture-error retries can restart authorization. Prompt enqueue is not prompt completion. |
| `jarvis/src/jarvis/audio/pipeline.py`; `jarvis/src/jarvis/audio/playback.py` | Interrupt stops current playback, not all synthesis, queues, or streamed producers. Existing playback has no verified echo-reference/AEC path. |
| `jarvis/src/jarvis/interpreter/schema.py`; `jarvis/src/jarvis/interpreter/golden.py`; `jarvis/src/jarvis/orchestrator/session.py` | Power-off is distinct from the required conversation closure; stored history already exists and is not open-session state. |

Baseline requirements needing focused deltas:
- `openspec/specs/voice-pipeline/spec.md` (RF-1/RF-4): distinguish wake standby from active conversation; replace blanket TTS-audio discard only when echo-safe interruption is accepted, preserving no self-trigger. Clarify intentionally interrupted spoken feedback without inventing a new latency SLA.
- `openspec/specs/assistant-lifecycle/spec.md` (RF-11): distinguish conversation closure, restart, and actual off; preserve off resource release and non-vocal reactivation.
- `openspec/specs/system-control/spec.md` (RF-5/RF-8/M6) and `openspec/specs/command-interpreter/spec.md`: specify prompt-completion-based expiration and stale-authorization rejection while preserving golden gates and action allowlists.

## Confirmed product rules

- After activation, ordinary first-speech waiting has no onset deadline. Long pauses do not end the active conversation. Unlimited waiting does not mean an unlimited spoken utterance or an endless audio recording.
- `terminamos` or `hasta luego`, used as an explicit goodbye, returns to wake-name standby; it does not power off or exit. The GUI off control retains its existing authority.
- Dangerous-action confirmation expires **15 seconds after prompt completion**, fails closed, and leaves the conversation open. Late yes cannot authorize expired work; technical retries cannot renew authorization indefinitely.
- Speaking over the assistant stops voice output and preserves new user speech without echo/self-trigger. It does not undo actions already executed.
- Restart requires new activation. Do not expand retention, providers, or speaker enrollment; do not retain endless silence/background recordings. Preserve existing authorization and history policies.
- Both integrated notebook audio and a headset with microphone are acceptance targets. Neither an existing barge-in flag nor assumed AEC establishes feasibility.

## Scope and approach: three sequential slices

Each slice is bounded, separately reviewable, and depends on acceptance of the previous slice. These are planning boundaries, not implementation authorization.

### 1. Cancellable indefinite waiting + finite safety confirmation

Separate waiting for speech onset from utterance collection. Discard idle silence or retain only bounded pre-roll; preserve finite post-onset utterance limits. Waiting must remain cancellable by off/shutdown and distinguish lack of frames from device failure.

Before enabling indefinite ordinary capture, give confirmation an independently enforceable finite deadline. Start its 15-second response window only after verified prompt completion; check validity before authorization and execution, including when capture/STT finishes late. Retries share a non-renewable authorization lifecycle. Prompt failure, cancellation, or unavailable completion evidence cannot authorize an action.

Likely affected areas: `audio/capture.py`, `audio/pipeline.py`, `orchestrator/confirm.py`, `orchestrator/loop.py`, and narrow capture/clock contracts under `jarvis/src/jarvis/`.

### 2. Persistent conversation + coordinated speaking/listening + explicit closure

Represent active conversation separately from wake standby and off. Replace the expiring one-shot follow-up allowance; coordinate completion and microphone readiness for replies, re-asks, and confirmations rather than relying on fixed sleeps. Preserve the active conversation through ordinary silence and recoverable turn failures without guessing commands.

Recognize explicit goodbye as conversation control, not a new agent action or `power_off_self`. Closing must invalidate pending authorization. Keep restart activation and GUI off behavior separate from persisted history. Before slice 3 is accepted, retain safe non-overlapping speaking/listening rather than promising speak-over support.

Likely affected areas: `orchestrator/loop.py`, narrow state/contracts/configuration and interpreter control routing as needed; regression coverage for `orchestrator/session.py`, not a history rewrite.

### 3. Fully cancelled speech output + echo-safe interruption

Coordinate cancellation across active playback, queued TTS, in-flight synthesis, and streamed response producers. Invalidated output must never restart; preserve the user's first speech rather than discarding it with assistant audio. Keep playback ownership and off precedence explicit. Audio interruption does not imply rollback of executed actions.

Likely affected areas: `audio/pipeline.py`, `audio/playback.py`, `audio/capture.py`, `orchestrator/loop.py`, and only necessary producer/wake/contracts integration.

**Acceptance gate:** keep interruption disabled until later authorized real-hardware verification demonstrates preserved user speech and no echo-driven activation/command dispatch on both targets. Unit tests, a raised wake threshold, speaker verification, or a legacy flag do not satisfy this gate. Headset-only or wake-only behavior is not fulfillment of the confirmed goal. Audio routing/AEC choices remain design risks; any required general backend rewrite requires renewed scope approval.

## Non-goals

No new agent commands, arbitrary actions, general audio-backend rewrite, provider migration, retention expansion, speaker enrollment, or history-storage redesign. No external research, implementation, tests, hardware probes, shell commands, automatic commits, or publication in this phase. Existing staged work, exploration, configuration, and `TAREAS.md` remain untouched.

## Risks and unresolved design gates

| Risk | Required treatment |
| --- | --- |
| Indefinite waiting stalls shutdown or accumulates audio | Bounded buffering, cancellation, and device-failure tests; preserve off resource release. |
| Prompt/capture/producer races authorize stale work or revive old speech | Explicit completion and cancellation ownership; deadline-before-authorization checks; bounded retry lifecycle and race tests. |
| Notebook loudspeaker echo resembles user speech | Real-device evidence for both targets before enabling slice 3; no claim that current AEC or barge-in solves it. |
| Goodbye text appears in dictation, quotation, or negation | Specify deterministic control precedence and regression scenarios; do not treat mentions as confirmed explicit closure. Exact parsing, acknowledgement, and concurrent-mode handling remain design decisions, not additional user approvals. |
| Longer listening changes privacy expectations | Preserve GUI off, existing speaker gates/providers/retention, and bounded idle buffers; do not promise unconditional locality beyond verified behavior. |
| Scope exceeds a bounded slice | Ask on risk before broadening architecture or exceeding the 800-line review budget; do not silently substitute reduced hardware support. |

## Success criteria and later verification

- After activation, silence beyond former onset/follow-up limits neither closes conversation nor grows retained idle audio; subsequent speech is accepted, and off cancels waiting.
- Replies longer than the former window, re-asks, and recoverable turn errors do not consume conversation availability. Explicit goodbye restores wake-name standby; restart needs activation; GUI off stops capture and wake reaction.
- A confirmation gets one finite 15-second response window after prompt completion. Expiry, late affirmative results, prompt failure, cancellation, and retries never execute stale work; timeout leaves ordinary conversation open.
- Interruption stops current and future output from the cancelled response, preserves new speech including its onset, and never undoes executed actions. Assistant-only playback does not activate or dispatch commands.
- The interruption criteria are demonstrated manually on integrated notebook audio **and** headset/mic hardware before slice 3 acceptance. No new numeric interruption-latency SLA is asserted.
- Later implementation follows strict TDD (RED, GREEN, TRIANGULATE, REFACTOR), with deterministic clock/capture/player/producer tests per slice. Existing unit areas in `jarvis/tests/unit/` include `test_audio_capture.py`, `test_audio_pipeline.py`, `test_audio_playback.py`, `test_confirm.py`, `test_loop.py`, `test_name_gate.py`, `test_golden.py`, `test_switch_signal.py`, and `test_session.py`. Automated evidence cannot replace the hardware gate. No tests were run for this proposal.

## Rollback

Keep the slices independently reversible. If interruption fails acceptance, leave it disabled and retain coordinated non-overlapping speaking/listening; report the unmet goal rather than declaring completion. If persistent sessions regress lifecycle behavior, restore wake-gated finite conversational behavior without altering stored history or staged work. Preserve the finite fail-closed confirmation fix during rollback; never restore stale-yes acceptance or endlessly renewable authorization. Off must still release audio resources. Select the concrete disable/revert mechanism during design, without adding a new backend here.

## Handoff and artifact authority

Proposal only: parent review and explicit user approval are required before specification/design work. Native status reports `artifactStore: openspec` and `nextRecommended: propose`; canonical session/config require **both**. Preserve this mismatch; save this proposal file and its equivalent Engram artifact under project `jarvis`, topic `sdd/jarvis-persistent-conversation/proposal`, following the explicit delegation rather than the config's `ale` bucket. Missing-artifact dependency values do not override the supplied planning authorization and do not authorize implementation.
