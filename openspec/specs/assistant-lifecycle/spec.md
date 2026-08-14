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

When off, the assistant MUST NOT listen, record, or react to the wake word. Reactivation MUST be non-vocal only (shortcut, command, or UI).

#### Scenario: Switch off stops recording

- GIVEN the switch is turned off
- WHEN ambient audio occurs
- THEN no audio MUST be captured
- AND the wake word MUST NOT trigger any reaction

#### Scenario: Non-vocal reactivation

- GIVEN the switch is off
- WHEN the user triggers the non-vocal reactivation (shortcut/command)
- THEN the assistant MUST resume listening
- AND a spoken wake word MUST NOT be able to reactivate it

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
