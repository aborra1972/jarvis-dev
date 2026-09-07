# system-control Specification

## Purpose

Executes OS control actions (shutdown, reboot, open app) behind a strict safety gate: verbal confirmation with 15s timeout (RF-5/RF-8, M6), application allowlist, and no arbitrary shell (M4). Executor is an in-process module (RNF-5).

## Requirements

### Requirement: Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)

[PC-S01] Shutdown and reboot MUST require verbal confirmation with a 15s timeout. Explicit refusal or timeout MUST abort the action. 100% of destructive actions, including power_off_self, MUST be confirmed before execution (M6). Each pending action MUST have one non-renewable authorization lifecycle: its response window starts only at verified completion of its entire confirmation prompt and expires 15 seconds later. Enqueue, elapsed sleep, or unverified flush MUST NOT establish prompt completion.

An affirmative MUST authorize only that same pending action, with verified prompt completion, and only while authorization is valid. At time equal to or later than the deadline, it MUST be expired. Validity MUST be checked before authorization and immediately before execution; late capture, STT, or classification results MUST NOT execute. Finite expiry MUST remain enforceable during blocked confirmation capture/STT independently of ordinary indefinite onset waiting.

Prompt failure or interruption, unavailable completion evidence, cancellation, goodbye, off, or loss of confirmation readiness MUST fail closed and invalidate pending authorization. Retries MUST NOT extend or reset the original deadline or create renewed authorization. Refusal, expiry, and recoverable failure MUST leave ordinary conversation open unless goodbye/off also applies. Already executed actions MUST NOT be undone by cancelling their spoken output.

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
- WHEN cancellation or GUI off invalidates the pending authorization before execution begins
- THEN the action MUST NOT execute even if that result later arrives before the former deadline

### Requirement: Open application (RF-8)

The system MUST open applications via xdg-open from a predefined allowlist. Applications outside the allowlist MUST be rejected.

#### Scenario: Allowed app

- GIVEN the user says "Jarvis, abrí Firefox"
- WHEN executed
- THEN Firefox MUST open

#### Scenario: Disallowed app

- GIVEN the user requests an application not in the allowlist
- WHEN evaluated
- THEN the system MUST reject it with a spoken message
- AND MUST NOT attempt to run it

### Requirement: No arbitrary shell (M4)

System actions MUST be limited to the allowlisted actions. The system MUST NOT expose or execute arbitrary shell commands.

#### Scenario: Shell-like request

- GIVEN the user says "Jarvis, corré apt update"
- WHEN evaluated
- THEN the system MUST reject it as unsupported
- AND MUST NOT spawn any shell
