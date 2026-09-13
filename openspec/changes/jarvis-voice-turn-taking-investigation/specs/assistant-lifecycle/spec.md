# Delta for assistant-lifecycle

## MODIFIED Requirements

### Requirement: Active conversation lifecycle

After a verified wake, the assistant MUST remain in active conversation across arbitrary ordinary pauses, recoverable STT failures, unsupported input, and re-ask cycles. The active conversation MUST end on an accepted exact standalone goodbye, GUI off, restart, or terminal shutdown. Exact standalone `terminamos` and exact standalone `hasta luego` MUST close the active conversation with both voice and text acknowledgement. Goodbye MUST return the assistant to wake-name standby, MUST invalidate stale work and pending confirmations from the prior conversation, and MUST NOT power off the process.
(Previously: Goodbye returned the assistant to wake-name standby and kept it powered on, but stale-work and pending-confirmation invalidation were not stated in this lifecycle requirement.)

#### Scenario: Active conversation persists

- GIVEN the assistant has verified a wake and completed a turn
- WHEN an arbitrary ordinary pause elapses
- THEN the assistant MUST remain ready for an ordinary request without another wake word

#### Scenario: Exact goodbye closes conversation

- GIVEN an active conversation
- WHEN the user says exactly `terminamos` or exactly `hasta luego` as a standalone utterance
- THEN the assistant MUST acknowledge the goodbye through voice and text
- AND MUST return to wake-name standby
- AND MUST remain powered on

#### Scenario: Goodbye invalidates stale work

- GIVEN an active conversation has pending confirmation, capture, execution, follow-up, or queued response work
- WHEN an accepted exact standalone goodbye closes the conversation
- THEN pending confirmation and stale volatile work from that conversation MUST be invalidated
- AND late results from that prior conversation MUST NOT execute, authorize, reopen follow-up, or speak into the next state

#### Scenario: Non-goodbye outcomes keep conversation active

- GIVEN an active conversation
- WHEN the user provides silence, unsupported input, a recoverable STT failure, or an unresolved request
- THEN the assistant MUST re-enter ordinary listening when ready
- AND MUST keep the conversation active

### Requirement: Goodbye and lifecycle precedence

GUI off MUST have stronger precedence than active conversation, goodbye, dictation, confirmation, output, and pending turn work. Off MUST stop capture and output, invalidate pending authorization and stale work, and leave the assistant off. Restart, non-vocal on, conversation close, or lifecycle restart MUST begin in wake-name standby and MUST require a fresh verified wake; active conversation MUST NOT resume across that boundary. Existing `power_off_self` semantics MUST remain unchanged: it MUST require the destructive confirmation gate and MUST stop the assistant process only after confirmed execution.
(Previously: GUI off precedence and fresh wake after off or restart were stated, but this requirement did not explicitly cover dictation/output precedence, conversation close/restart boundaries, or preservation of `power_off_self`.)

#### Scenario: Off wins over goodbye

- GIVEN active conversation or a goodbye is being processed
- WHEN GUI off occurs
- THEN capture and output MUST be cancelled
- AND pending authorization MUST be invalidated
- AND the assistant MUST remain off without sending a goodbye acknowledgement

#### Scenario: Off wins over dictation and confirmation

- GIVEN dictation or destructive confirmation is active
- WHEN GUI off occurs
- THEN dictation capture and confirmation capture MUST stop
- AND pending authorization and stale in-flight work MUST be invalidated
- AND the assistant MUST remain off

#### Scenario: On requires fresh wake

- GIVEN the assistant is off, has restarted, or has closed an active conversation
- WHEN the user speaks an ordinary request without the wake word
- THEN the assistant MUST NOT process it
- WHEN the user provides a fresh verified wake
- THEN a new active conversation MAY begin

#### Scenario: power_off_self remains distinct from goodbye

- GIVEN the user asks Jarvis to power itself off
- WHEN the request passes the existing golden gate and verbal confirmation
- THEN `power_off_self` MUST stop the assistant process
- AND this behavior MUST NOT be replaced by goodbye standby behavior

### Requirement: Deletable local logs (RNF-3, RF-11)

Transcripts and audio MUST be stored locally only and MUST be deletable on demand via a command. Voice turn-taking changes MUST preserve the existing history shape and redaction expectations; stale or invalidated work MUST NOT create successful command-history entries.
(Previously: Local-only storage and cleanup were required, but turn-taking invalidation and history-shape preservation were not stated.)

#### Scenario: Local-only storage

- GIVEN the assistant has processed commands
- THEN transcripts and audio MUST reside only on the local machine

#### Scenario: Log cleanup

- GIVEN logs exist
- WHEN the user issues the cleanup command
- THEN transcripts and audio MUST be deleted
- AND the assistant MUST confirm deletion (spoken + text)

#### Scenario: Stale work does not change successful history

- GIVEN stale work is invalidated by goodbye, GUI off, fresh wake, or epoch replacement
- WHEN a late result arrives
- THEN it MUST NOT be recorded as a successful command turn
- AND existing history schema and redaction behavior MUST be preserved
