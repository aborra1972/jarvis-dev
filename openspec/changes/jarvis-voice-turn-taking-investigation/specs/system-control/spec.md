# Delta for system-control

## MODIFIED Requirements

### Requirement: Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)

[PC-S01] Shutdown and reboot MUST require verbal confirmation with a 15s timeout. Explicit refusal or timeout MUST abort the action. 100% of destructive actions, including power_off_self, MUST be confirmed before execution (M6). Each pending action MUST have one non-renewable authorization lifecycle: its response window starts only at verified completion of its entire confirmation prompt and expires 15 seconds later. Enqueue, elapsed sleep, or unverified flush MUST NOT establish prompt completion.

An affirmative MUST authorize only that same pending action, with verified prompt completion, and only while authorization is valid. At time equal to or later than the deadline, it MUST be expired. Validity MUST be checked before authorization and immediately before execution; late capture, STT, classification, stale-epoch, goodbye, or GUI-off results MUST NOT execute. Finite expiry MUST remain enforceable during blocked confirmation capture/STT independently of ordinary indefinite onset waiting.

Prompt failure or interruption, unavailable completion evidence, cancellation, goodbye, off, epoch replacement, or loss of confirmation readiness MUST fail closed and invalidate pending authorization. Retries MUST NOT extend or reset the original deadline or create renewed authorization. Refusal, expiry, and recoverable failure MUST leave ordinary conversation open unless goodbye/off also applies. Already executed actions MUST NOT be undone by cancelling their spoken output.
(Previously: Confirmation failed closed for cancellation, goodbye, off, and readiness loss, but stale epoch replacement and turn-taking readiness were not explicit in the destructive-action safety requirement.)

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
- AND the system MUST return to ordinary listening when input is available

#### Scenario: Prompt completion starts the window

- GIVEN a prompt remains queued, synthesizing, or playing, even beyond 15s since enqueue
- WHEN the entire prompt completes with verified evidence and the microphone is ready for confirmation
- THEN the deadline MUST be 15s after verified completion, not enqueue
- AND no affirmative from before verified completion MUST authorize the action

#### Scenario: Exact expiry boundary

- GIVEN verified prompt completion at time T and no prior invalidation
- WHEN authorization is evaluated at T + 15s or later
- THEN it MUST be rejected as expired, including an affirmative arriving exactly at T + 15s

#### Scenario: Late recognition or delayed execution

- GIVEN the user starts saying "sí" before expiry
- WHEN capture/STT/classification finishes at or after expiry, or authorization reaches execution only at or after expiry
- THEN the action MUST NOT execute
- AND the late result MUST NOT authorize another pending action

#### Scenario: Cancellation defeats stale affirmative

- GIVEN a dangerous action awaits confirmation and an affirmative result is in flight
- WHEN cancellation, GUI off, goodbye, or epoch replacement invalidates the pending authorization before execution begins
- THEN the action MUST NOT execute even if that result later arrives before the former deadline

#### Scenario: Turn-taking changes preserve destructive safety

- GIVEN voice turn-taking changes affect capture timing, readiness barriers, follow-up, or barge-in
- WHEN a destructive action or `power_off_self` requires confirmation
- THEN the existing golden gate and verbal confirmation requirements MUST still apply
- AND no turn-taking path MAY bypass or renew destructive authorization
