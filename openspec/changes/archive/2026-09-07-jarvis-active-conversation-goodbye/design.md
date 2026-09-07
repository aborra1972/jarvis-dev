# Design: Loop-owned active conversation with explicit goodbye

## Decision first

Extend the existing orchestrator loop with a loop-owned active-conversation lifecycle. A verified wake creates an active epoch; ordinary capture remains available across arbitrary pauses and recoverable input outcomes. Only the exact standalone transcripts `terminamos` and `hasta luego` close the conversation. The close is acknowledged in voice and text, invalidates pending confirmation, and returns to wake-name standby without powering off the process. GUI off and terminal lifecycle events remain stronger authorities.

This is a design artifact only. No source, test, configuration, task, or apply change is included here.

## Scope and invariants

- Standby is wake-gated; active turns use `CaptureMode.ORDINARY`.
- Ordinary waiting has bounded pre-roll/retention and finite post-onset VAD limits; it is not an unbounded audio recording.
- Silence, `NO_FRAME`, recoverable STT errors, unsupported input, unresolved input, and re-asks preserve the active epoch.
- `power_off_self` remains a separate golden-gated, finite-confirmation terminal action.
- Active conversation, goodbye, and confirmation never outrank GUI off; off cancels capture/output and invalidates authorization.
- Restart and GUI/on create a new standby epoch; no active state is resumed.
- Existing PR1–PR3 wake gating, cancellation, history, confirmation safety, non-overlap, and no-self-trigger behavior remain unchanged.

## Existing seams and planned file responsibilities

| Existing file / symbol | Design use | Planned change boundary |
|---|---|---|
| `jarvis/src/jarvis/orchestrator/loop.py:_Context`, `_tick`, `run` | Single lifecycle owner, capture/interpret/confirm/execute sequencing | Replace deadline authority with explicit active state/epoch and lifecycle decisions; retain compatibility deadline only if needed for rollback |
| `jarvis/src/jarvis/orchestrator/state.py:State`, `Event`, `transition` | Existing coarse FSM and GUI/terminal transitions | Add only the smallest active/close events or document active as loop context; do not create a second owner |
| `jarvis/src/jarvis/audio/capture.py:gather_utterance_result` | Bounded idle pre-roll, finite utterance, cancellation polling | Reuse `CaptureMode.ORDINARY`; no onset timeout or retained idle growth |
| `jarvis/src/jarvis/audio/pipeline.py:UtteranceCapture.capture` | Adapter for ordinary/confirmation capture and operation cancellation | Pass active epoch operation token; preserve separate finite confirmation mode |
| `jarvis/src/jarvis/audio/pipeline.py:PiperSpeaker.speak_and_wait`, `flush`, `is_playing` | Prompt completion evidence and playback boundary | Use explicit completion plus mic-ready barrier; do not infer readiness from sleeps alone |
| `jarvis/src/jarvis/interpreter/interpreter.py:resolve_intent`, `Interpretation` | Narrow pre-intent control routing | Emit a lifecycle control result before LLM/golden ordinary intent processing |
| `jarvis/src/jarvis/interpreter/normalize.py` | Boundary normalization only | Normalize case/whitespace/transcript boundaries without broadening accepted phrases |
| `jarvis/src/jarvis/interpreter/dictation.py:DictationManager.process_transcript` | Existing dictation control/data seam | Check standalone goodbye before content insertion; preserve quoted/mentioned/negated/content text as data |
| `jarvis/src/jarvis/orchestrator/confirm.py:Authorization.invalidate/consume` | Token-bound safety gate | Invalidate on goodbye before any late verdict; retain final consume validation and fixed deadline |
| `jarvis/src/jarvis/orchestrator/session.py:record_turn/save` | Existing history semantics | Preserve format and reload behavior; do not invent history entries for lifecycle metadata unless existing policy requires it |
| `jarvis/src/jarvis/orchestrator/loop.py:_apply_switch` | Main-loop off authority | Keep off processing before interpretation, confirmation, acknowledgement, and execution |
| `jarvis/src/jarvis/config.py:CONVERSATION_WINDOW_S`, `AUDIO_*`, `BARGE_IN_ENABLED` | Compatibility and existing audio knobs | Add at most an explicit active-mode/ack configuration; do not use a larger timeout as the design |

## Lifecycle, state, and epoch ownership

The loop owns one `ConversationContext` (an extension of `_Context`) containing:

```text
lifecycle: STANDBY | ACTIVE_WAITING | PROCESSING | CONFIRMING | ACKNOWLEDGING
active_epoch: monotonically increasing identifier, or None in standby
operation: existing OperationToken for the current capture/turn
authorization: existing token-bound Authorization, if confirmation is pending
```

The existing coarse FSM remains authoritative for `OFF`, `STOPPED`, execution, and speaking. If adding enum states creates duplicate ownership, keep lifecycle as context plus explicit events and publish the coarse state as today. Invariants:

1. Only verified wake in standby creates `active_epoch`.
2. Every capture, STT result, interpretation, confirmation verdict, and acknowledgement carries the current operation/epoch identity.
3. Goodbye clears active state and increments/invalidates the epoch before acknowledgement is queued.
4. Off clears active state, cancels the operation, invalidates authorization, and suppresses acknowledgement.
5. A stale result can never transition lifecycle, consume authorization, write a command result, or execute.
6. Restart/on initializes standby and does not deserialize active listening state.

```text
OFF --non-vocal on/restart--> STANDBY
STANDBY --verified wake--> ACTIVE_WAITING
ACTIVE_WAITING --ordinary utterance--> PROCESSING
PROCESSING --ordinary result/re-ask/error--> ACK/BARRIER --> ACTIVE_WAITING
PROCESSING --exact goodbye--> STANDBY + voice/text ack
PROCESSING/CONFIRMING --goodbye--> ACTIVE_WAITING (authorization invalidated)
any non-terminal state --GUI off--> OFF (cancel + invalidate, no ack)
CONFIRMING --valid affirmative--> EXECUTING --> ACK/BARRIER --> ACTIVE_WAITING
EXECUTING --power_off_self--> STOPPED
```

## Data flow and control classification

```text
wake detector (standby only)
  -> verified wake + epoch
  -> ordinary capture (bounded idle / finite onset utterance)
  -> transcript + operation/epoch
  -> deterministic goodbye classifier
       | exact standalone: lifecycle control
       | otherwise: dictation classifier or existing resolve_intent
  -> session.next_step / existing safety gates
  -> confirmation (separate finite mode) or execution
  -> text event + TTS acknowledgement/reply
  -> completion/readiness barrier
  -> next ordinary capture
```

The classifier accepts only normalized text equal to one of two exact strings. It must reject all longer or uncertain surfaces, including `dijo hasta luego`, `la frase terminamos`, `no terminamos`, `escribí "hasta luego"`, reported speech, mention, quotation, negation, and mixed content. No LLM, fuzzy matching, aliases, politeness variants, or general command intent may authorize closure. Ambiguity follows existing interpretation/re-ask behavior.

Dictation precedence is explicit: classify the exact standalone direct utterance before calling `process_transcript`; consume it as control and do not append it. Any quoted, mentioned, reported, negated, or content occurrence is passed to the existing dictation data path. Existing `enviar`, exit-dictation, and clear controls retain their current scope and do not become goodbye aliases.

A goodbye during confirmation is not affirmative, refusal, cancellation, or destructive execution. It atomically invalidates the current `Authorization` with reason `goodbye`, invalidates the operation/epoch used by confirmation capture, and returns to active ordinary listening after readiness. GUI off checked at the same boundary wins and emits neither goodbye text nor voice.

## Readiness barrier and races

All active recapture paths—reply, re-ask, goodbye acknowledgement, confirmation prompt, and recoverable STT response—use one coordinator barrier:

1. Confirm the operation/epoch is still current and not cancelled.
2. Keep microphone capture closed while TTS is playing.
3. Obtain explicit `speak_and_wait` completion/failure evidence (or the existing narrowly accepted production adapter).
4. Flush wake and stale capturer buffers using existing bounded flush behavior.
5. Start the capturer and verify the adapter's ready/start contract.
6. Re-check GUI off, terminal state, cancellation, and epoch before entering ordinary capture.

A fixed sleep is only a hardware settling aid after verified completion, never the correctness contract. If completion or readiness cannot be established, fail closed: do not dispatch captured audio or consume authorization; surface the existing safe error and return to standby or active waiting according to the stronger lifecycle event.

Race table:

| Race | Required winner/result |
|---|---|
| Off during capture/STT | Cancel token, discard result, invalidate auth, OFF; no ack |
| Off with goodbye transcript | Off; no ack and no active-state mutation after OFF |
| Goodbye while confirmation capture runs | Goodbye invalidates auth; late verdict rejected; active waiting |
| Late affirmative after goodbye | `Authorization.consume` fails by state/token/epoch |
| Restart/on during old playback/result | New standby epoch; old result and playback completion cannot reactivate |
| TTS completion after close/off | Completion may clean up only; it cannot transition or speak after off |
| Ordinary silence after active turn | Return to cancellable active waiting, never wake scan |
| Stale queued mic audio after playback | Flush before recapture; never interpret it |

## Interfaces and contracts

Conceptual interfaces, expressed as narrow extensions of existing seams:

```python
class GoodbyeControl(Protocol):
    def classify(self, transcript: str) -> bool: ...  # exact, deterministic

class ReadinessBarrier(Protocol):
    def after_speech(self, *, operation, epoch) -> bool: ...

class ConversationContext:
    active_epoch: int | None
    def begin_after_verified_wake(self) -> int: ...
    def close_goodbye(self) -> None: ...
    def reset_to_standby(self) -> None: ...
```

The concrete loop must continue accepting injected fakes for clock, wake, capture, speaker, interpreter, executor, switch, and session. Goodbye is a lifecycle result, not an allowlisted executor intent. Text acknowledgement is emitted through the existing GUI/state/event reporting seam; voice uses the configured speaker. Exact acknowledgement wording is a single configuration/constant seam and must be emitted only while the epoch is still active and off has not won.

## Configuration and observability

Retain `CONVERSATION_WINDOW_S` for compatibility/rollback, but active mode must not derive correctness from its expiration or set it to an arbitrarily large value. If a flag is required, use an explicit active-conversation rollout switch defaulting to the approved product behavior, with no new goodbye aliases. Existing `AUDIO_PREROLL_S`, `AUDIO_FLUSH_MS`, VAD bounds, and `BARGE_IN_ENABLED=False` remain authoritative.

Log structured lifecycle events at INFO and race/stale drops at DEBUG/WARN without logging raw audio or changing retention: `conversation.activated(epoch)`, `turn.waiting`, `goodbye.accepted(source=voice|dictation)`, `goodbye.rejected(reason=nonstandalone|ambiguous)`, `confirmation.invalidated(reason=goodbye)`, `barrier.ready/failed`, `stale_result_dropped(epoch)`, and `off_precedence`. GUI state strings remain compatible (`idle`, `listening`, `speaking`, `confirming`, `off`, `stopped`); active detail may be added without changing persistence.

## Strict-TDD verification plan

Tests are implementation work, not part of this artifact. The strict sequence is:

1. **RED:** add deterministic tests for exact phrases, boundary normalization, quoted/mentioned/negated/content rejection, dictation precedence, long ordinary pause, silence/STT/re-ask persistence, and fresh wake after on/restart.
2. **RED:** add race tests for off-vs-goodbye, goodbye-vs-late-confirmation, stale epoch results, prompt/readiness failure, stale-buffer flushing, and no capture during TTS.
3. **GREEN:** implement the smallest loop/context and deterministic classifier changes through injected seams.
4. **TRIANGULATE:** run focused orchestrator/interpreter/audio/confirmation suites, then the full existing suite; verify history, golden destructive commands, cancellation, wake gating, and non-overlap regressions.
5. **REFACTOR:** centralize barrier and precedence checks, remove deadline-based active authority, keep compatibility switch and logs clear, and rerun all focused and full tests.

No hardware, AEC, barge-in, queued TTS cancellation, provider, or timing claim is test acceptance for this change.

## Rollout, rollback, and failure policy

Roll out behind one lifecycle decision point while preserving the existing operation token and off path. During staged rollout, observe activation/close/stale-drop/barrier metrics and compare wake-gating and confirmation regressions. Rollback disables active mode and restores finite follow-up/wake-gated behavior; it must not restore renewable confirmation windows or accept late affirmatives. Parser or barrier failure fails closed to standby/active re-ask as appropriate, never executes an ambiguous command, and never persists resumable active listening.

## Non-goals

Barge-in, AEC, playback interruption, queued TTS cancellation, hardware support, provider/backend replacement or rewrite, retention changes, history redesign, new commands or goodbye aliases, LLM-authorized closure, wake-gating changes in standby, `power_off_self` changes, and resumable active state across restart/on are explicitly excluded.
