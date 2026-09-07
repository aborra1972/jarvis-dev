# Delta for Voice Pipeline

## ADDED Requirements

### Requirement: Active conversation uses bounded ordinary capture

After a verified wake activation, the voice pipeline MUST keep ordinary conversation capture available across arbitrary pauses without requiring another wake word. Each turn MUST reuse ordinary capture with unbounded pre-onset waiting, finite post-onset utterance limits, bounded idle retention, cancellation polling, and the existing playback-to-microphone readiness barrier. Confirmation capture MUST remain separate and finite.

#### Scenario: Speech after an arbitrary pause

- GIVEN a verified wake has established an active conversation
- WHEN the user speaks an ordinary request after an arbitrary silent pause
- THEN the request MUST be captured without another wake word
- AND its post-onset audio MUST remain within the existing finite utterance bound

#### Scenario: Active conversation remains open after recoverable input

- GIVEN an active conversation
- WHEN ordinary capture produces silence, a recoverable STT failure, unsupported input, or a re-ask
- THEN the pipeline MUST return to cancellable ordinary listening
- AND MUST NOT require a new wake word solely because of that outcome

#### Scenario: Playback readiness prevents overlap

- GIVEN the assistant has spoken an acknowledgement, reply, or re-ask
- WHEN the next active turn begins
- THEN capture MUST start only after verified playback completion and microphone readiness
- AND TTS audio MUST NOT be transcribed as user input or trigger the wake word

#### Scenario: Stronger lifecycle interruption

- GIVEN active conversation capture is waiting or collecting speech
- WHEN GUI off, shutdown, or cancellation occurs
- THEN capture MUST terminate promptly
- AND the cancelled or interrupted result MUST NOT dispatch a command

## MODIFIED Requirements

### Requirement: Wake word activation (RF-1)

The system MUST gate entry into an active conversation on detection of the configured wake word ("Jarvis" by default, configurable) using the local wake-word detector. Audio without the wake word MUST be ignored while in wake-name standby. Once active conversation is established, subsequent ordinary turns MUST NOT require another wake word until goodbye, GUI off, restart, or another terminal lifecycle interruption.
(Previously: Every audio processing path was gated on wake-word detection and activation transitioned only to command capture.)

#### Scenario: Activation and continued conversation

- GIVEN the assistant is in wake-name standby
- WHEN the user says "Jarvis, abrí OpenCode"
- THEN the remainder MUST be transcribed and the assistant MUST enter active conversation
- AND a later ordinary request after a long pause MUST be accepted without "Jarvis"

#### Scenario: Standby remains wake-gated

- GIVEN the assistant is in wake-name standby
- WHEN ambient speech does not contain the configured wake word
- THEN the assistant MUST NOT activate, transcribe, or process it as a command

#### Scenario: Fresh activation after reset

- GIVEN the assistant has restarted or has been reactivated through GUI/on
- WHEN ordinary speech occurs without a fresh wake word
- THEN it MUST be ignored
- AND only a new verified wake word MAY establish active conversation
