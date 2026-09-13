# Delta for voice-pipeline

## ADDED Requirements

### Requirement: Readiness barrier before listening

The system MUST use one readiness barrier before every ordinary, follow-up, reask, and confirmation capture. The barrier MUST verify that queued or active TTS playback has completed, post-playback cooldown has elapsed, wake buffers have been flushed, capture buffers have been flushed, and microphone capture is ready. Fixed sleeps alone MUST NOT be treated as readiness evidence.

#### Scenario: Ordinary capture waits for readiness

- GIVEN Jarvis has enqueued or is playing spoken output
- WHEN the next ordinary listening turn is requested
- THEN capture MUST NOT start until TTS is no longer queued or active
- AND capture MUST NOT start until cooldown, wake-buffer flush, capture-buffer flush, and microphone readiness have completed

#### Scenario: Confirmation and reask use the same barrier

- GIVEN Jarvis speaks a confirmation prompt or reask prompt
- WHEN it waits for the user's response
- THEN response capture MUST start only after the same readiness barrier succeeds
- AND the prompt MUST NOT be transcribed as user input

#### Scenario: Barrier cancellation fails closed

- GIVEN the readiness barrier is preparing capture
- WHEN GUI off, shutdown, or operation cancellation occurs before readiness succeeds
- THEN capture MUST NOT begin
- AND any pending operation or authorization MUST be invalidated when applicable

### Requirement: Follow-up window starts after playback completion

The system MUST anchor follow-up availability to the actual completion of the user-visible spoken response that opens the follow-up opportunity. Time spent synthesizing, queueing, or playing that response MUST NOT consume the follow-up window.

#### Scenario: Long spoken response preserves follow-up time

- GIVEN a command succeeds and Jarvis has a long spoken response
- WHEN the response finishes playing
- THEN the follow-up window MUST begin at that playback completion time
- AND the user MUST receive the configured follow-up duration after Jarvis is audibly done speaking

### Requirement: Barge-in clears interrupted speech

If barge-in is enabled, the system MUST stop active TTS playback and clear queued pending TTS for the interrupted epoch. Interrupted or stale queued speech MUST NOT resume after the user barges in.

#### Scenario: Queued speech cannot resume after barge-in

- GIVEN barge-in is enabled and Jarvis has active playback plus queued TTS
- WHEN the user triggers a valid barge-in
- THEN active playback MUST stop
- AND queued pending TTS for the interrupted turn MUST be discarded
- AND listening MUST proceed without replaying stale speech

### Requirement: Active epoch invalidates stale turn work

The system MUST associate volatile turn work with the current active conversation epoch. Late capture, STT, interpretation, confirmation, execution, or TTS results from an inactive epoch MUST NOT dispatch commands, authorize destructive actions, update follow-up state, or resume speech.

#### Scenario: Late result after epoch replacement is ignored

- GIVEN epoch A has pending work
- WHEN a fresh wake or lifecycle close replaces epoch A with epoch B or standby
- THEN late results from epoch A MUST be ignored
- AND they MUST NOT execute actions or enqueue speech for the new state

## MODIFIED Requirements

### Requirement: Separate speech-onset waiting from utterance endpoint (PC-V04)

Ordinary capture MUST distinguish initial silence before first detected speech from trailing silence after speech has started. Ordinary capture MAY wait without a speech-onset deadline when an active conversation is intentionally waiting for the next turn, but initial silence MUST NOT consume the finite post-onset utterance duration or trigger phrase endpoint detection. Post-wake finite capture modes MUST use an initial-silence policy that is independent from trailing-silence cutoff and long enough for a normal post-wake pause. After speech starts, the existing finite utterance cap and phrase endpoint behavior MUST remain in force. Idle audio retention MUST have a finite bound independent of wait duration; indefinite waiting MUST NOT accumulate recordings of silence or background audio. Dangerous-action confirmation MUST use its finite deadline before indefinite ordinary waiting is enabled.
(Previously: Ordinary capture required separated onset waiting and finite endpoints, but did not explicitly distinguish post-wake initial-silence policy from trailing-silence cutoff for all turn-taking paths.)

#### Scenario: Indefinite onset wait

- GIVEN ordinary capture is waiting after activation
- WHEN silence continues beyond former onset limits and speech then begins
- THEN capture MUST still accept the speech
- AND the pre-onset wait MUST NOT shorten its post-onset utterance duration

#### Scenario: Initial silence does not count as trailing silence

- GIVEN Jarvis has become ready to listen after wake feedback
- WHEN the user pauses briefly before first speech
- THEN capture MUST remain open under the applicable initial-silence policy
- AND trailing-silence endpoint detection MUST NOT begin until speech has started

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
