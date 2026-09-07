# Delta for System Control

## Scope and traceability

Approved proposal slice 1, with closure/cancellation integration from slices 2–3. Existing requirement name remains the archive key; PC-S01 is the stable reference. Open application (RF-8) and No arbitrary shell (M4) remain unchanged. The golden rule gate remains independent and authoritative.

## MODIFIED Requirements

### Requirement: Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)

[PC-S01] Shutdown and reboot MUST require verbal confirmation with a 15s timeout. Explicit refusal or timeout MUST abort the action. 100% of destructive actions, including power_off_self, MUST be confirmed before execution (M6). Each pending action MUST have one non-renewable authorization lifecycle: its response window starts only at verified completion of its entire confirmation prompt and expires 15 seconds later. Enqueue, an elapsed sleep, or unverified flush MUST NOT establish prompt completion.

An affirmative MUST authorize only that same pending action, with verified prompt completion, and only while the authorization is valid. At time equal to or later than the deadline, it MUST be expired. Validity MUST be checked before authorization and before execution; speech starting or being captured in time MUST NOT authorize an action if capture/STT/classification finishes too late or execution has not begun before expiry. Finite expiry MUST remain enforceable during blocked capture/STT independently of unlimited ordinary speech-onset waiting.

Prompt failure/interruption, unavailable completion evidence, cancellation, goodbye, off, or loss of readiness to collect confirmation MUST fail closed and invalidate pending authorization. Capture/STT failure retries and prompt replays MUST NOT extend/reset the original deadline or create renewed authorization for the same pending action. Before verified completion, failed/unverifiable prompting MUST NOT enter an indefinitely renewing retry lifecycle. A new authorization lifecycle MUST require a fresh explicit dangerous-action request through the existing gates, not a late affirmative or technical retry. Refusal, expiry, and recoverable failure MUST leave ordinary conversation open unless goodbye/off also applies. Already executed actions MUST NOT be undone by cancelling their spoken output.
(Previously: A nominal 15s verbal-confirmation timeout was required, without prompt-completion origin, equality boundary, late-result rejection, or non-renewable retry semantics.)

#### Scenario: Confirmed

- GIVEN the user says "Jarvis, cerrá Linux" and the existing golden gate approves the request
- WHEN the system completes "¿confirmás que apago la máquina?", the user says "sí", and authorization and execution both occur before the 15s deadline with no invalidation
- THEN the system MUST shut down

#### Scenario: Refused

- GIVEN a confirmation prompt is open
- WHEN the user says "no"
- THEN the action MUST be aborted
- AND no shutdown/reboot MUST occur

#### Scenario: Timeout aborts

- GIVEN the confirmation prompt completed and its response window is open
- WHEN no valid affirmative is available before 15s elapse
- THEN the action MUST be aborted (M6), including while capture/STT remains blocked
- AND the system MUST return to ordinary listening with the conversation open when input is available

#### Scenario: Prompt completion starts the window

- GIVEN a prompt remains queued, synthesizing, or playing, even beyond 15s since enqueue
- WHEN the entire prompt completes with verified evidence and the microphone is ready for confirmation
- THEN the deadline MUST be 15s after that verified completion, not after enqueue
- AND no affirmative from before verified completion MUST authorize the action

#### Scenario: Exact expiry boundary

- GIVEN verified prompt completion at time T and no prior invalidation
- WHEN authorization is evaluated at T + 15s or later
- THEN it MUST be rejected as expired, including an affirmative result arriving exactly at T + 15s

#### Scenario: Late recognition or delayed execution

- GIVEN the user starts saying "sí" before expiry
- WHEN capture/STT/classification finishes at or after expiry, or otherwise-valid authorization reaches execution only at or after expiry
- THEN the action MUST NOT execute
- AND the late result MUST NOT authorize another pending action

#### Scenario: Prompt cannot establish authorization

- GIVEN a dangerous action is pending
- WHEN its prompt fails, is interrupted, lacks verified completion evidence, or confirmation input cannot become ready
- THEN the action MUST fail closed without authorization
- AND retries MUST NOT keep that pending authorization renewable indefinitely
- AND ordinary conversation MUST remain open unless goodbye/off applies

#### Scenario: Retry does not renew consent

- GIVEN the prompt completed at T and a capture/STT error causes a retry or prompt replay
- WHEN the same pending action is reconsidered
- THEN its deadline MUST NOT move beyond T + 15s
- AND invalidated authorization MUST NOT be revived
- AND a late "sí" without a fresh dangerous-action request MUST NOT start another authorization lifecycle

#### Scenario: Cancellation or goodbye defeats stale affirmative

- GIVEN a dangerous action awaits confirmation and an affirmative result is in flight
- WHEN cancellation, explicit goodbye, or GUI off invalidates the pending authorization before execution begins
- THEN the action MUST NOT execute even if that result later arrives before the former deadline
- AND goodbye MUST return to wake standby while off MUST retain its stronger no-listening behavior

#### Scenario: Interruption does not reverse execution

- GIVEN an action already executed under valid authorization
- WHEN the user interrupts its spoken result
- THEN the audio MUST stop under PC-V06 when enabled
- AND interruption MUST NOT undo the action or imply that execution was cancelled
