# Delta for System Control

## MODIFIED Requirements

### Requirement: Shutdown/reboot verbal confirmation (RF-5, RF-8, M6)

[PC-S01] Shutdown, reboot, and `power_off_self` MUST retain the existing golden recognition, verbal confirmation, non-renewable 15-second authorization, cancellation, final validity check, and fail-closed execution rules. An accepted standalone goodbye MUST invalidate any pending confirmation authorization before a late affirmative or execution can be consumed. Goodbye MUST NOT execute, cancel, or alter the requested destructive action as a replacement command; after invalidation, ordinary conversation remains active unless GUI off or a terminal lifecycle event also applies.
(Previously: Confirmation interruption included cancellation, off, and readiness loss but did not specify goodbye invalidation or its conversation consequence.)

#### Scenario: Goodbye invalidates pending confirmation

- GIVEN a destructive action has a pending confirmation and its prompt has completed
- WHEN the user provides the exact standalone goodbye control
- THEN the pending authorization MUST be invalidated
- AND a later affirmative MUST NOT authorize or execute the action
- AND ordinary conversation MUST remain active

#### Scenario: Goodbye during confirmation capture fails closed

- GIVEN confirmation capture or STT is in progress for a destructive action
- WHEN standalone goodbye is recognized before execution
- THEN the action MUST NOT execute
- AND the pending authorization MUST be invalidated
- AND the assistant MUST return to ordinary active conversation when ready

#### Scenario: Off remains stronger

- GIVEN a pending destructive confirmation and active conversation
- WHEN GUI off occurs before or with goodbye handling
- THEN capture and output MUST be cancelled
- AND authorization MUST be invalidated
- AND no destructive action or goodbye acknowledgement MUST be emitted
- AND the assistant MUST remain off

#### Scenario: Existing confirmation safety is preserved

- GIVEN a destructive request is golden-table approved
- WHEN no goodbye, cancellation, off, or terminal interruption occurs
- THEN only a valid affirmative received and consumed before the verified 15-second deadline MAY execute the action
- AND timeout, refusal, late recognition, prompt failure, or ambiguous input MUST fail closed
