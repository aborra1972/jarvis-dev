# Delta for Assistant Lifecycle

## Scope and traceability

Approved proposal slices 1–2 and off precedence in slice 3. Existing names remain archive keys; PC-L identifiers are stable references. Manual start, Help, Voice power-off, and Deletable local logs remain unchanged. Conversation closure is not power-off or a history-storage change.

## MODIFIED Requirements

### Requirement: On/off switch (RF-11)

[PC-L01] When off, the assistant MUST NOT listen, record, or react to the wake word. Reactivation MUST be non-vocal only (shortcut, command, or UI). GUI off MUST cancel pending capture and authorization, stop output, and release audio resources irrespective of conversation, confirmation, or interruption state. Late completions MUST NOT reactivate processing or dispatch cancelled work. Non-vocal reactivation MUST return to wake standby, not restore an open conversation or pending authorization.
(Previously: Off prohibited listening/recording/wake reaction and required non-vocal reactivation, without explicit active-conversation or concurrent-work precedence.)

#### Scenario: Switch off stops recording

- GIVEN the switch is turned off
- WHEN ambient audio occurs
- THEN no audio MUST be captured
- AND the wake word MUST NOT trigger any reaction

#### Scenario: Non-vocal reactivation

- GIVEN the switch is off
- WHEN the user triggers non-vocal reactivation (shortcut/command/UI)
- THEN the assistant MUST resume listening in wake standby
- AND a spoken wake word MUST NOT be able to reactivate it while off

#### Scenario: Off during pending work

- GIVEN the conversation is waiting indefinitely, confirming, speaking, or processing an interruption
- WHEN GUI off occurs, including concurrently with a capture/STT/synthesis/stream completion
- THEN pending capture and authorization MUST be cancelled, voice output MUST stop, and audio resources MUST be released
- AND late work MUST NOT resume listening/playback or dispatch a cancelled action while off

## ADDED Requirements

### Requirement: Persistent active conversation and explicit closure

[PC-L02] Successful activation MUST open a conversation that remains open across ordinary silence, completed turns, long replies, re-asks, and recoverable turn failures until explicit goodbye or off. Explicit goodbye under PC-C01 MUST close it, invalidate pending authorization, and return to wake standby without powering off or exiting. Neither closure nor interruption MUST undo an already executed action. Restart MUST require fresh activation; stored history MUST NOT restore open listening or pending authorization. Existing history, provider, retention, and speaker-gate policies MUST remain unchanged; this feature MUST NOT introduce speaker enrollment.

#### Scenario: Activation without an immediate command

- GIVEN the assistant is in wake standby
- WHEN activation succeeds and the user waits through a long silence before speaking
- THEN the conversation MUST remain open and accept the later ordinary turn without repeating the wake word

#### Scenario: Long pause between turns

- GIVEN an ordinary turn completed or a recoverable turn error was handled
- WHEN the user pauses beyond former follow-up limits
- THEN ordinary silence MUST NOT close the conversation
- AND the next turn MUST NOT require fresh activation

#### Scenario: Goodbye restores standby

- GIVEN an active conversation with or without pending authorization
- WHEN the user explicitly says "terminamos" or "hasta luego" as conversation control
- THEN the conversation MUST close and pending authorization MUST become invalid
- AND the process MUST remain running in wake standby, not off
- AND subsequent command speech without activation MUST be ignored in standby
- AND a fresh wake activation MUST be able to open a new conversation

#### Scenario: Restart does not restore an open conversation

- GIVEN a conversation was open and history exists before restart
- WHEN the assistant starts again
- THEN it MUST require fresh wake activation before command capture
- AND it MUST NOT restore pending authorization or infer an open conversation from stored history
- AND history storage and reload behavior MUST remain unchanged

#### Scenario: Confirmation expiry is not goodbye

- GIVEN a dangerous-action confirmation expires or fails closed
- WHEN the pending action is aborted and ordinary input is available
- THEN the conversation MUST remain open unless an explicit goodbye or off also occurred
- AND the aborted action MUST NOT be resumed by later speech
