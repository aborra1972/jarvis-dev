# Exploration: active conversation with explicit goodbye

## Status and boundary

Exploration complete for a distinct change, `jarvis-active-conversation-goodbye`. This is planning evidence only; no source, test, specification, configuration, archived artifact, research, or `TAREAS.md` file was edited. The only created artifact is this file.

- Repository root: `/media/ale/Windows/Users/aleja/Documents/Proyectos/jarvis-dev`.
- Required follow-up scope: persistent active conversation after wake, indefinite ordinary pauses through the verified PR1 capture seam, explicit `terminamos` / `hasta luego`, lifecycle precedence, confirmation invalidation, coordinated reply/re-ask microphone readiness, and existing history preservation.
- `skill_resolution: paths-injected`; both injected skill files were read before exploration.
- Archived predecessor `openspec/changes/archive/2026-09-07-jarvis-persistent-conversation/` was read as historical context. It is not reopened.
- Current repository specs read read-only: `voice-pipeline`, `assistant-lifecycle`, `command-interpreter`, and `system-control`.
- No tests were run and no implementation is authorized by this artifact.

## Product outcome to design

After one successful wake activation, Jarvis remains in an active conversational mode across ordinary silence, including pauses longer than the former follow-up window. It returns to wake-name standby only after an explicit goodbye control or lifecycle interruption. Ordinary indefinite waiting is not an unbounded recording: PR1's `CaptureMode.ORDINARY` waits for onset with bounded pre-roll, then applies finite trailing-silence and maximum-utterance limits. Confirmation remains a separate finite, fail-closed capture mode.

Recommended user-visible contract:

| Input or event | Result | Precedence |
|---|---|---|
| Wake activation while standby | Enter active conversation and capture the current turn | Wake gating remains mandatory in standby |
| Ordinary silence or recoverable STT/re-ask cycle | Keep active conversation open; wait again without requiring the name | Does not authorize or execute anything |
| Exact explicit `terminamos` or `hasta luego` | Acknowledge if product approves, invalidate pending confirmation, return to wake-name standby | Conversation close, not shutdown or process exit |
| Quoted, reported, or negated goodbye | Treat as user content, not closure | Must not close accidentally |
| Goodbye while dictation is active | Product must choose whether explicit control wins or dictation text wins; default recommendation is control only when the utterance is an unquoted standalone goodbye | Dictation must not make ordinary text unexpectedly execute |
| GUI/off switch | Stop capture, release audio, invalidate operation and authorization, and remain off | Stronger than active conversation or goodbye |
| Non-vocal restart/on | Resume the service in wake-name standby; require fresh activation | Voice cannot reactivate an off assistant |
| `power_off_self` | Preserve its existing golden recognition and confirmation, then stop the process only after valid authorization | Never alias to conversation close |

The phrase parser/control event must be distinct from `power_off_self`, from action cancellation, and from stopping playback. No new general command is proposed.

## Concrete repository evidence

| Evidence path | Finding | Design consequence |
|---|---|---|
| `jarvis/src/jarvis/audio/capture.py:gather_utterance_result` | PR1 now exposes `CaptureMode.ORDINARY` and `CaptureMode.CONFIRMATION`; ordinary mode has no onset deadline, bounded `idle_preroll_blocks`, finite post-onset VAD limits, cancellation polling, and distinct `NO_FRAME`/device-failure outcomes. | Reuse this seam; do not resurrect timeout inflation or the legacy tuple helper. Active mode needs a lifecycle cancellation predicate but no ordinary onset deadline. |
| `jarvis/src/jarvis/audio/pipeline.py:UtteranceCapture.capture` | The adapter passes mode, deadline, operation, and clock to PR1; cancellation prevents dispatch, empty captures are not transcribed, and finite audio is removed after STT. | Ordinary active turns can use the verified PR1 path. Confirmation must continue passing `CaptureMode.CONFIRMATION` and its authorization deadline. |
| `jarvis/src/jarvis/orchestrator/loop.py:_Context` | `conversation_until` and `conversation_after_playback` implement only a deadline-based follow-up window. IDLE clears it when expired and then invokes wake detection. | Replace expiry as the ordinary-session authority with explicit active-conversation state; retain a reversible compatibility path during rollout. |
| `jarvis/src/jarvis/orchestrator/loop.py` | A follow-up enters `LISTENING` without wake gating, but only while `conversation_until` is live. Successful replies set the pending flag before playback and compute the deadline after playback ends. | Preserve the useful post-playback anchor, but remove expiration for ordinary active sessions and apply the same state after silence, re-asks, and recoverable failures. |
| `jarvis/src/jarvis/orchestrator/loop.py` re-ask branch | A re-ask calls `speaker.speak(...)` and immediately returns `LISTENING`; the normal IDLE speaking gate is bypassed. | Re-asks need one coordinated speak-complete → stale-buffer flush → mic-ready barrier, not a fixed sleep. |
| `jarvis/src/jarvis/orchestrator/loop.py` reply and `PiperSpeaker` | Normal reply flow passes through `SPEAKING`/IDLE and keeps the mic stopped while playback is active. `PiperSpeaker.speak_and_wait` exists, but is implemented through queue flush plus a completion-shaped result. | Use the explicit completion seam where its evidence is accepted; do not claim arbitrary backend completion or enable barge-in. Define behavior for prompt failure/readiness loss as fail closed. |
| `jarvis/src/jarvis/orchestrator/confirm.py:Authorization` | Authorization is token-bound, has a one-time verified prompt-completion deadline, rejects `now >= deadline`, and supports invalidation. | Goodbye/off must call invalidation before a late affirmative can be consumed. Confirmation retries must reuse the same record and never renew the window. |
| `jarvis/src/jarvis/orchestrator/loop.py:_apply_switch` | Off cancels the operation, invalidates authorization, saves state, closes speaker, and invokes the injected switch. | Off precedence is already a strong seam; active-conversation work must not bypass it or allow late workers to dispatch. |
| `jarvis/src/jarvis/interpreter/golden.py` and `schema.py` | The golden table recognizes destructive intents, including `power_off_self`; no goodbye intent/control exists. LLM output is allowlisted and destructive suggestions require the golden gate. | Add a narrow deterministic control-routing seam before ordinary intent execution, without making goodbye an executor command or weakening the golden gate. |
| `jarvis/src/jarvis/orchestrator/state.py` | FSM has IDLE/LISTENING/CONFIRMING/EXECUTING/SPEAKING/OFF/STOPPED, but no active-conversation state or close event. | Either add explicit lifecycle state/events or keep active status as a loop-owned context with documented invariants; avoid a second uncoordinated FSM. |
| `jarvis/src/jarvis/orchestrator/session.py` | History is persisted immediately by `record_turn`; active listening state is not stored as conversation history. | Preserve record format, reload behavior, and turn timing. Goodbye may be a control event and need not create a fake command turn. |
| Current specs | Voice pipeline requires wake gating and no self-trigger; lifecycle gives off and non-vocal reactivation authority; system control requires finite confirmation; interpreter requires re-ask and no partial execution. | The change is a focused delta to lifecycle/voice/control/interpreter behavior, not a provider, retention, history, or backend redesign. |

## Proposed lifecycle and ownership

Use a single loop-owned `ConversationContext` (or equivalent extension of `_Context`) with explicit states/invariants:

```text
OFF --non-vocal on--> STANDBY
STANDBY --verified wake--> ACTIVE_WAITING
ACTIVE_WAITING --ordinary onset--> PROCESSING
PROCESSING --reply/reask/error--> SPEAKING_BARRIER or ACTIVE_WAITING
ACTIVE_WAITING --standalone goodbye--> STANDBY
ACTIVE/PROCESSING/CONFIRMING --off/shutdown--> OFF or STOPPED by existing authority
```

The active flag is established only by wake activation and is cleared by explicit goodbye, off, restart, or terminal power-off. Ordinary silence, `NO_FRAME`, unsupported input, failed re-asks, and recoverable STT errors do not clear it. Each capture/reply operation receives the existing operation token; off, goodbye, and replacement operations invalidate it, and late results are ignored. Off is checked at the top of each tick and before capture, interpretation, confirmation acceptance, and execution.

For every response or re-ask, the coordinator must own this sequence: stop or keep the mic closed as appropriate, obtain verified completion/failure from the speaker seam, flush stale wake/capture buffers, reopen the mic, then enter ordinary active capture. Correctness must not depend on a guessed sleep duration. If completion or microphone readiness cannot be established, fail closed for confirmation and return to a safe active/standby state without dispatching a transcript.

## Goodbye control distinctions requiring specification

The control recognizer should operate on normalized transcript text but retain enough surface/context information to distinguish control from content. Recommended deterministic cases:

- Accept only a standalone, direct utterance whose normalized content is exactly `terminamos` or `hasta luego` (optionally with approved politeness/filler only after product confirmation).
- Do not close for quotation/reporting such as “dijo hasta luego”, “la frase terminamos”, or a request to write/say those words.
- Do not close for negation such as “no digas hasta luego” or “no terminamos”; negation remains content unless the parser cannot prove intent, in which case fail closed and keep the conversation open.
- In dictation, do not consume words as a control unless the product explicitly chooses the standalone-direct exception; a quoted phrase must be inserted as text.
- During pending confirmation, goodbye must invalidate the authorization and leave the assistant in active conversation (unless off or power-off precedence applies); it must not be classified as affirmative or refusal.
- “Pará”, “cancelá”, “no”, and similar words remain action/confirmation controls only where their existing context defines them; they are not new goodbye aliases.

Ambiguous or mixed utterances should re-ask rather than close or execute. The exact acknowledgement text, accepted punctuation/filler, whether goodbye is recorded in history, and dictation precedence require product confirmation before proposal/spec work.

## Risks and alternatives

| Risk | Treatment / alternative |
|---|---|
| Indefinite waiting blocks shutdown or device recovery | Keep operation cancellation and PR1 polling; distinguish `NO_FRAME` and device failure; off remains authoritative. A finite idle health watchdog may detect dead hardware but must not become a speech-onset timeout. |
| Assistant listens while its queued reply or re-ask is still playing | Centralize the completion/readiness barrier. Alternative is retaining wake-gated/non-overlap behavior until the barrier exists; fixed sleeps alone are rejected. |
| Goodbye closes on quoted, negated, or dictated text | Deterministic standalone control parser with conservative fail-closed ambiguity handling; never delegate closure to an unconstrained LLM. |
| Late confirmation authorizes after close/off | Invalidate the same token-bound `Authorization` before accepting results and retain final `consume` validation. |
| Active state accidentally survives restart or off | Do not persist active conversational state as resumable listening state; restart/on lands in standby and requires fresh wake. |
| History changes or duplicates during control transitions | Keep `Session.record_turn` and file format unchanged; decide explicitly whether a goodbye control is metadata-only or a non-action turn. |
| New lifecycle state duplicates existing FSM ownership | Prefer one loop owner and explicit events/context; if `state.py` changes, make transitions table-driven and preserve OFF/STOPPED precedence. |
| Scope drifts into audio interruption | Keep microphone closed during TTS, preserve no-self-trigger and non-overlap, and exclude barge-in/AEC, queued TTS cancellation, and hardware acceptance. |

Alternatives rejected: merely setting `CONVERSATION_WINDOW_S` to a huge value (still timer-driven and does not solve re-ask readiness); treating goodbye as `power_off_self` (unsafe and violates lifecycle semantics); routing goodbye through the LLM (ambiguous and unsafe); persisting “active” across process restart (unexpected listening/privacy risk); redesigning history or replacing the audio backend (unnecessary for this slice).

## Product decisions requiring confirmation

1. Are only exact standalone `terminamos` and `hasta luego` accepted, or are polite variants accepted too?
2. Should explicit goodbye be acknowledged by voice, text only, or silently return to wake standby?
3. Does a goodbye during pending confirmation always invalidate and keep active conversation open, and does it produce a history entry?
4. Does standalone goodbye win over active dictation, or must dictation always receive the words? How are quoted and negated forms represented by the dictation UI?
5. Should unsupported input and exhausted re-asks keep the active session open indefinitely, with the same PR1 capture mode?
6. Is restart defined as process restart, GUI “on”, or both, and must every such path require a new wake activation? (Recommendation: yes.)
7. Is any visible listening indicator or mute affordance needed for the longer active period, without changing existing retention/provider policy?

## Success criteria for the next phases

- A wake opens active conversation; silence longer than the former onset/follow-up limits does not close it and does not grow retained idle audio.
- Speech after an arbitrarily long ordinary pause is captured through `CaptureMode.ORDINARY`; post-onset audio remains bounded and finite.
- Replies, re-asks, confirmations, recoverable errors, and silence all reach a microphone-ready barrier before the next capture; no assistant playback is transcribed or dispatched.
- Exact approved goodbye closes only the active conversation; quoted, negated, ambiguous, and disallowed dictation mentions do not close it.
- Goodbye invalidates pending confirmation; off wins over goodbye and cancels capture/output; restart/on requires fresh wake; `power_off_self` retains its separate golden confirmation and terminal behavior.
- Existing history persistence and reload tests remain unchanged in format and semantics; no new retention or provider behavior is introduced.
- Deterministic tests cover long pauses, operation cancellation, readiness races, goodbye distinctions, precedence, stale confirmations, re-asks, and history regression. No hardware or barge-in claim is made.

## Rollback and handoff

Keep the active-session policy behind a narrow lifecycle decision point so rollback can restore wake-gated finite follow-up behavior without reverting PR1's bounded ordinary capture or fail-closed confirmation. On any readiness or parser regression, disable explicit active mode and require wake activation while retaining off cancellation, authorization invalidation, non-overlap, and history behavior. Never roll back to late affirmative acceptance or renewable confirmation deadlines.

Next phase: proposal clarification/interview, beginning with the seven product decisions above. After confirmation, produce a focused proposal/spec delta and design; implementation remains out of scope for this exploration. The later design must name the exact control-routing seam, active-state owner, completion/readiness contract, and rollback switch before tasks are created.
