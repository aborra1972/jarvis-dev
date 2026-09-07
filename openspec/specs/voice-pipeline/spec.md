# voice-pipeline Specification

## Purpose

Voice front/back end of the voice→action bridge: wake word gating (RF-1), local STT (RNF-2/M3), local TTS (RF-4), latency budget (RNF-1/M2), and no self-trigger. One of the 5 runtime components (RNF-5): audio+VAD, STT, interpreter, orchestrator, TTS.

## Requirements

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

### Requirement: Local STT (RNF-2, M3)

The system MUST transcribe Spanish rioplatense utterances locally using whisper-cli small (language `es`, beam 1, VAD, domain `--prompt`). Accuracy MUST meet ≥90% WER (M3).

#### Scenario: Correct transcription

- GIVEN the user says "cerrá Linux"
- WHEN STT processes the utterance
- THEN the transcript MUST contain the exact command tokens

#### Scenario: Domain prompt bias

- GIVEN the domain prompt is loaded
- WHEN the utterance contains technical vocabulary (e.g. "middleware de auth")
- THEN transcription MUST preserve the technical terms

#### Scenario: STT failure

- GIVEN whisper-cli fails or times out
- WHEN no transcript is produced
- THEN the system MUST report a spoken error and re-enter listening
- AND MUST NOT guess the intended command

### Requirement: Spoken + text feedback (RF-4)

The system MUST respond to every command with spoken output (piper `es_AR-daniela`) AND on-screen text.

#### Scenario: Dual feedback

- GIVEN a command completed
- WHEN the orchestrator produces the result
- THEN the result MUST be spoken and shown as text

### Requirement: Latency budget (RNF-1, M2)

The voice→first-action pipeline MUST complete in <6s (M2). Non-LLM commands SHOULD complete in <3s (RNF-1 objective). Commands estimated over 3s MUST emit a spoken acknowledgment before the long operation.

#### Scenario: Non-LLM command within budget

- GIVEN a system/file/web command
- WHEN the user finishes the utterance
- THEN the first visible action MUST occur within 6s

#### Scenario: Long LLM operation

- GIVEN an OpenCode/LLM command estimated over 3s
- WHEN the orchestrator starts execution
- THEN it MUST speak an acknowledgment (e.g. "dale, te aviso") before the operation

### Requirement: No self-trigger

While TTS output is playing, the system MUST discard captured audio.

#### Scenario: Assistant speaking

- GIVEN TTS is speaking a response
- WHEN audio is captured during playback
- THEN the audio MUST be dropped
- AND it MUST NOT trigger the wake word

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

### Requirement: Separate speech-onset waiting from utterance endpoint (PC-V04)

Ordinary capture MUST wait without a speech-onset deadline and MUST remain cancellable. Pre-onset silence MUST NOT consume the finite post-onset utterance duration or trigger phrase endpoint detection. After speech starts, the existing finite utterance cap and phrase endpoint behavior MUST remain in force. Idle audio retention MUST have a finite bound independent of wait duration; indefinite waiting MUST NOT accumulate recordings of silence or background audio. Dangerous-action confirmation MUST use its finite deadline before indefinite ordinary waiting is enabled.

#### Scenario: Indefinite onset wait

- GIVEN ordinary capture is waiting after activation
- WHEN silence continues beyond former onset limits and speech then begins
- THEN capture MUST still accept the speech
- AND the pre-onset wait MUST NOT shorten its post-onset utterance duration

#### Scenario: Finite utterance after onset

- GIVEN speech has begun
- WHEN the existing phrase endpoint or finite post-onset duration cap is reached
- THEN the utterance MUST end under the applicable endpoint policy
- AND the capture MUST NOT become an unlimited recording

#### Scenario: Bounded idle retention

- GIVEN ordinary capture is waiting without speech onset
- WHEN idle waiting continues repeatedly
- THEN retained idle audio MUST remain within its finite bound
- AND idle/background audio MUST NOT become a persistent recording

#### Scenario: Cancelled or failed capture

- GIVEN capture is waiting for onset or collecting speech
- WHEN cancellation, GUI off, or shutdown occurs
- THEN capture MUST terminate without waiting for speech or an endpoint
- AND cancelled results MUST NOT dispatch a command
- GIVEN a transient no-frame read occurs without device failure
- THEN it MUST NOT be treated as a completed utterance
- GIVEN the audio device fails
- THEN capture MUST report failure without fabricating a transcript or executing a guessed command
