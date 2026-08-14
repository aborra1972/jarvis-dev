# voice-pipeline Specification

## Purpose

Voice front/back end of the voice→action bridge: wake word gating (RF-1), local STT (RNF-2/M3), local TTS (RF-4), latency budget (RNF-1/M2), and no self-trigger. One of the 5 runtime components (RNF-5): audio+VAD, STT, interpreter, orchestrator, TTS.

## Requirements

### Requirement: Wake word activation (RF-1)

The system MUST gate all audio processing on detection of the configured wake word ("Jarvis" by default, configurable) using a local wake-word detector (openWakeWord). Audio that does not contain the wake word MUST be ignored.

#### Scenario: Activation

- GIVEN the assistant is listening
- WHEN the user says "Jarvis, abrí OpenCode"
- THEN the system MUST transition to command capture
- AND the remainder of the utterance MUST be transcribed

#### Scenario: False activation from ambient voice

- GIVEN the assistant is listening
- WHEN ambient conversation does not include the wake word
- THEN the system MUST NOT activate
- AND no audio MUST be transcribed or processed as a command

#### Scenario: Noise rejection

- GIVEN the assistant is listening
- WHEN background noise (keyboard, music) occurs without speech
- THEN the system MUST NOT activate
- AND the STT MUST NOT be invoked on silence (VAD gate)

#### Scenario: Configurable wake word

- GIVEN the user configured a custom wake word
- WHEN the user speaks the configured word
- THEN activation MUST use the configured word

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
