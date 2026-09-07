# assistant-lifecycle Specification

## Purpose

Controls the assistant's own lifecycle: manual start (MVP), voice power-off, help, on/off switch (RF-11), and deletable local logs (RNF-3). Owns the orchestrator state machine (idle/listening/confirming/executing/speaking), which is one of the 5 runtime components (RNF-5).

## Requirements

### Requirement: Manual start (MVP)

The assistant MUST start with the `jarvis start` command. Auto-start at login is out of MVP scope.

#### Scenario: Start

- GIVEN the user runs `jarvis start`
- WHEN startup completes
- THEN the pipeline (audio+VAD, STT, interpreter, orchestrator, TTS) MUST be active
- AND the assistant MUST announce readiness (TTS + text)

### Requirement: Help

The assistant MUST answer `help` by listing the supported commands (spoken + text).

#### Scenario: Help request

- GIVEN the user says "Jarvis, qué sabés hacer"
- WHEN resolved
- THEN the system MUST speak and show the list of the 15 commands

### Requirement: Voice power-off

The assistant MUST power off on `power_off_self` ("Jarvis, apagate"). It MUST NEVER reactivate itself by voice.

#### Scenario: Voice power-off

- GIVEN the user says "Jarvis, apagate"
- WHEN the command is confirmed
- THEN the process MUST stop
- AND audio resources MUST be released

### Requirement: On/off switch (RF-11)

When off, the assistant MUST NOT listen, record, process speech, or react to the wake word. Reactivation MUST be non-vocal only, and reactivation MUST start in wake-name standby rather than restoring any prior active conversation. GUI off MUST be authoritative over capture, output, confirmation, and goodbye handling.
(Previously: Non-vocal reactivation resumed listening without specifying fresh-wake or precedence behavior.)

#### Scenario: Switch off is authoritative

- GIVEN the assistant is active, confirming, speaking, or waiting for ordinary input
- WHEN the GUI switch is turned off
- THEN audio capture and output MUST stop or be cancelled
- AND the wake word and any late result MUST have no effect

#### Scenario: Non-vocal reactivation

- GIVEN the assistant is off
- WHEN the user triggers non-vocal reactivation
- THEN the assistant MUST resume in wake-name standby
- AND spoken audio MUST NOT reactivate it
- AND a fresh verified wake MUST be required before ordinary conversation

### Requirement: Deletable local logs (RNF-3, RF-11)

Transcripts and audio MUST be stored locally only and MUST be deletable on demand via a command.

#### Scenario: Local-only storage

- GIVEN the assistant has processed commands
- THEN transcripts and audio MUST reside only on the local machine

#### Scenario: Log cleanup

- GIVEN logs exist
- WHEN the user issues the cleanup command
- THEN transcripts and audio MUST be deleted
- AND the assistant MUST confirm deletion (spoken + text)

### Requirement: Active conversation lifecycle

After a verified wake, the assistant MUST remain in active conversation across arbitrary ordinary pauses, recoverable STT failures, unsupported input, and re-ask cycles. The active conversation MUST end on an accepted standalone goodbye, GUI off, restart, or terminal shutdown. Goodbye MUST return the assistant to wake-name standby; it MUST NOT power off the process.

#### Scenario: Active conversation persists

- GIVEN the assistant has verified a wake and completed a turn
- WHEN an arbitrary ordinary pause elapses
- THEN the assistant MUST remain ready for an ordinary request without another wake word

#### Scenario: Goodbye closes conversation

- GIVEN an active conversation
- WHEN the user says the exact standalone phrase "terminamos" or "hasta luego"
- THEN the assistant MUST acknowledge the goodbye through voice and text
- AND MUST return to wake-name standby
- AND MUST remain powered on

#### Scenario: Non-goodbye outcomes keep conversation active

- GIVEN an active conversation
- WHEN the user provides silence, unsupported input, a recoverable STT failure, or an unresolved request
- THEN the assistant MUST re-enter ordinary listening when ready
- AND MUST keep the conversation active

### Requirement: Goodbye and lifecycle precedence

GUI off MUST have stronger precedence than active conversation or goodbye. Off MUST stop capture and output, invalidate pending authorization, and leave the assistant off. Restart or non-vocal on MUST begin in wake-name standby and MUST require a fresh verified wake; active conversation MUST NOT resume across that boundary.

#### Scenario: Off wins over goodbye

- GIVEN active conversation or a goodbye is being processed
- WHEN GUI off occurs
- THEN capture and output MUST be cancelled
- AND pending authorization MUST be invalidated
- AND the assistant MUST remain off without sending a goodbye acknowledgement

#### Scenario: On requires fresh wake

- GIVEN the assistant is off or has restarted
- WHEN the user speaks an ordinary request without the wake word
- THEN the assistant MUST NOT process it
- WHEN the user provides a fresh verified wake
- THEN a new active conversation MAY begin
