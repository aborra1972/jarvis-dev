# Delta for Voice Pipeline

## Scope and traceability

Approved proposal slices 1–3. Existing requirement names remain archive keys; PC-V identifiers are stable references. Wake gating changes only for an activated conversation. True barge-in replaces blanket TTS-audio discard only after PC-V06 acceptance. Local STT and Latency budget (RNF-1, M2), including acknowledgment and timing clauses, remain unchanged. No new latency SLA, endpoint tuning, provider, retention, or enrollment policy is introduced.

## MODIFIED Requirements

### Requirement: Wake word activation (RF-1)

[PC-V01] In wake standby, the system MUST gate command audio processing on detection of the configured wake word ("Jarvis" by default, configurable) using the existing local wake-word detector (openWakeWord). Audio without the wake word MUST be ignored for transcription and commands in standby. After activation, the system MUST accept ordinary conversation turns without another wake word until explicit conversation closure or off. Existing speaker and action authorization gates MUST remain authoritative.
(Previously: All audio processing was wake-gated and audio without the wake word was ignored, without an active-conversation exception.)

#### Scenario: Activation

- GIVEN the assistant is in wake standby
- WHEN the user says "Jarvis, abrí OpenCode"
- THEN the system MUST transition to command capture and open the conversation
- AND the remainder of the utterance MUST be transcribed

#### Scenario: False activation from ambient voice

- GIVEN the assistant is in wake standby
- WHEN ambient conversation does not include the wake word
- THEN the system MUST NOT activate
- AND no audio MUST be transcribed or processed as a command

#### Scenario: Noise rejection

- GIVEN the assistant is listening
- WHEN background noise (keyboard, music) occurs without speech
- THEN the system MUST NOT activate
- AND STT MUST NOT be invoked on silence (VAD gate)

#### Scenario: Configurable wake word

- GIVEN the user configured a custom wake word
- WHEN the user speaks the configured word in standby
- THEN activation MUST use the configured word

#### Scenario: Follow-up without activation repetition

- GIVEN an activated conversation remains open across a long pause
- WHEN the user speaks a new ordinary turn without the wake word
- THEN the system MUST capture that turn subject to existing speaker and authorization gates

### Requirement: Spoken + text feedback (RF-4)

[PC-V02] The system MUST respond to every command with spoken output (piper `es_AR-daniela`) AND on-screen text. Intentional interruption or off MUST stop the affected spoken output rather than require its completion or replay. Audio interruption MUST NOT suppress the on-screen result of an already completed command or undo its action.
(Previously: Every result had unconditional spoken and text feedback, without an intentional audio-cancellation exception.)

#### Scenario: Dual feedback

- GIVEN a command completed and its feedback is not cancelled
- WHEN the orchestrator produces the result
- THEN the result MUST be spoken and shown as text

#### Scenario: Interrupted result is not rollback

- GIVEN a command has executed and its result is being spoken
- WHEN the user interrupts the response
- THEN the affected spoken output MUST stop without replaying its cancelled remainder
- AND the completed command result MUST remain available as text
- AND the executed action MUST NOT be undone by audio interruption

### Requirement: No self-trigger

[PC-V03] Assistant-generated audio, including residual echo, MUST NOT activate the assistant, create a user turn, authorize an action, or dispatch a command. Until PC-V06 is satisfied, the system MUST discard captured audio during TTS playback and retain safe non-overlapping speaking/listening. With accepted interruption enabled in an active conversation, the system MUST preserve actual user speech during playback rather than discard all captured audio, while excluding assistant audio from user input.
(Previously: All captured audio during TTS was dropped to prevent wake activation; accepted barge-in requires preserving overlapping user speech without weakening no-self-trigger.)

#### Scenario: Assistant speaking

- GIVEN TTS is speaking a response and interruption is not accepted/enabled
- WHEN audio is captured during playback
- THEN the audio MUST be dropped
- AND it MUST NOT trigger the wake word

#### Scenario: Speaker-only echo

- GIVEN accepted interruption is enabled and no user is speaking
- WHEN assistant audio containing the wake name, a command, an affirmative, or a goodbye reaches the microphone during playback or as residual echo
- THEN it MUST NOT cause activation, a user turn, interruption, confirmation, closure, or command dispatch

#### Scenario: Readiness beep is not user input

- GIVEN the assistant emits a readiness or follow-up beep and no user is speaking
- WHEN the beep or its residual audio reaches the microphone
- THEN it MUST NOT be transcribed as user input, trigger activation or a user turn, authorize an action, or dispatch a command
- AND in non-overlapping mode, listening readiness MUST be established only after the beep completes and its residual audio is excluded from user input

#### Scenario: User speech overlaps the assistant

- GIVEN accepted interruption is enabled in an active conversation
- WHEN the user starts speaking during TTS without repeating the wake word
- THEN the response MUST be interrupted and the user's new speech, including its onset, MUST be preserved for the next turn
- AND assistant audio MUST NOT become part of the user's command or confirmation

## ADDED Requirements

### Requirement: Separate speech-onset waiting from utterance endpoint

[PC-V04] Ordinary capture in an active conversation MUST wait without a speech-onset deadline and MUST remain cancellable. Pre-onset silence MUST NOT consume the finite post-onset utterance duration or trigger phrase endpoint detection. After speech starts, the existing finite utterance cap and phrase endpoint behavior MUST remain in force. Idle audio retention MUST have an identifiable finite bound independent of wait duration; indefinite waiting MUST NOT accumulate recordings of silence/background audio. Dangerous-action confirmation MUST instead obey PC-S01's finite deadline before indefinite ordinary waiting is enabled.

#### Scenario: Indefinite onset wait

- GIVEN ordinary capture is waiting after activation
- WHEN silence continues beyond former onset/follow-up limits and speech then begins
- THEN capture MUST still accept the speech
- AND the pre-onset wait MUST NOT shorten its available post-onset utterance duration

#### Scenario: Phrase endpoint and duration cap remain finite

- GIVEN speech has begun
- WHEN the existing phrase endpoint is reached or the finite post-onset duration cap is reached
- THEN the utterance MUST end under the existing applicable endpoint policy
- AND the open conversation MUST NOT become an unlimited single recording

#### Scenario: Bounded idle retention

- GIVEN the configured or established finite idle-buffer bound
- WHEN idle waiting is extended repeatedly without speech onset
- THEN retained idle audio MUST remain within that same bound rather than grow with elapsed wait time
- AND this feature MUST NOT add persistent idle/background recordings

#### Scenario: Cancel waiting or collecting

- GIVEN capture is waiting for onset or collecting speech
- WHEN cancellation, GUI off, or shutdown occurs
- THEN capture MUST terminate without waiting for speech or a phrase endpoint
- AND cancelled capture/STT results MUST NOT dispatch a command

#### Scenario: Missing frames versus device failure

- GIVEN ordinary capture is waiting for speech
- WHEN a transient no-frame read occurs without device failure
- THEN it MUST NOT be treated as a completed utterance or conversation closure
- AND cancellation MUST remain available
- GIVEN the audio device instead fails
- WHEN that failure is detected
- THEN the system MUST end the failed capture and report the failure rather than wait indefinitely as if it were silence
- AND it MUST NOT fabricate a transcript or execute a guessed command

### Requirement: Listening readiness after assistant speech

[PC-V05] Ordinary replies and re-asks MUST leave the active conversation available regardless of their duration. In non-overlapping mode, the system MUST coordinate actual output completion and microphone readiness before accepting the next turn; enqueue, elapsed sleeps, or an unverified flush MUST NOT establish completion. Confirmation readiness and failure MUST additionally obey PC-S01. Recoverable capture/STT/turn failures MUST NOT close the conversation or cause guessed execution; the existing re-ask limit and manual-correction fallback remain unchanged.

#### Scenario: Long reply or re-ask

- GIVEN the active conversation is using non-overlapping output and a reply or re-ask outlasts the former follow-up window
- WHEN all relevant output actually completes and the microphone becomes ready
- THEN ordinary speech-onset waiting MUST remain available without a new wake word or onset deadline
- AND queued/in-flight speech MUST NOT consume that availability

#### Scenario: Unverified completion or microphone failure

- GIVEN output completion is not verified or the microphone cannot become ready
- WHEN the next capture would otherwise begin
- THEN the system MUST NOT claim a ready listening turn based only on enqueue or elapsed time
- AND it MUST report a detected failure without authorizing pending dangerous work

#### Scenario: Recoverable turn failure

- GIVEN an active conversation encounters a recoverable capture or STT error
- WHEN the error is reported and input becomes ready again
- THEN the conversation MUST remain open without renewed activation
- AND the failed turn MUST NOT be guessed or executed

### Requirement: Complete response interruption and hardware acceptance

[PC-V06] When enabled, speech interruption MUST stop all voice output belonging to the cancelled response: active playback, queued speech, in-flight synthesis, and subsequently arriving streamed output. Invalidated output MUST NOT resume. New user speech MUST be preserved independently of the cancelled response. Cancellation ownership and concurrency mechanisms are left to design; GUI off MUST take precedence over output/capture resumption. Already executed actions MUST NOT be rolled back by interruption.

Interruption MUST remain disabled until actual hardware evidence demonstrates preserved user speech and no assistant-audio self-trigger on BOTH integrated notebook audio and a headset with microphone. A legacy flag, raised wake threshold, speaker verification, assumed echo cancellation, automated-only evidence, or success on only one target MUST NOT satisfy acceptance. Wake-only interruption MUST NOT be represented as fulfillment. Until acceptance, PC-V03's non-overlapping mode MUST remain available.

#### Scenario: Cancellation across output stages

- GIVEN a response has active playback, queued sentences, an in-flight synthesis result, or an active streamed producer
- WHEN user speech interrupts it
- THEN active voice output from that response MUST stop
- AND queued output, late synthesis completion, and later stream chunks from that response MUST NOT start or restart playback
- AND the user's new speech onset MUST be retained for its own turn

#### Scenario: Off wins an interruption race

- GIVEN interruption and late synthesis/stream completion overlap with GUI off
- WHEN off takes effect
- THEN no participant MUST restart playback, capture, or wake processing while off
- AND late capture/STT work MUST NOT dispatch a command

#### Scenario: Evidence gate

- GIVEN no actual passing evidence exists for both required hardware targets
- WHEN interruption enablement or slice acceptance is evaluated
- THEN interruption MUST remain disabled and the unmet goal MUST be reported
- GIVEN actual evidence on both targets covers overlapping user speech including onset, cancellation across output stages, and assistant-only playback/residual echo without self-trigger
- WHEN acceptance is evaluated
- THEN only that complete evidence MAY satisfy the hardware gate
