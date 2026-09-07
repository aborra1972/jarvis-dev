# Delta for Command Interpreter

## ADDED Requirements

### Requirement: Deterministic standalone goodbye control

The interpreter MUST recognize only the exact standalone utterances `terminamos` and `hasta luego` as the goodbye control. Goodbye recognition MUST be deterministic, MUST NOT depend on an LLM, and MUST fail closed for ambiguous, quoted, mentioned, reported, negated, or content occurrences. A goodbye MUST be routed as lifecycle control rather than as a new general or destructive command.

#### Scenario: Exact goodbye

- GIVEN an active conversation
- WHEN the transcript is exactly `terminamos` or exactly `hasta luego`, ignoring only permitted transcript boundary normalization
- THEN the interpreter MUST emit the goodbye control
- AND MUST NOT emit an ordinary action intent

#### Scenario: Content is not goodbye

- GIVEN an active conversation
- WHEN the transcript contains a goodbye phrase as part of a longer request, quotation, mention, report, negation, or ambiguous text
- THEN the interpreter MUST NOT emit goodbye
- AND the transcript MUST remain available to ordinary interpretation or re-ask handling

### Requirement: Goodbye precedence in dictation

During dictation, a standalone approved goodbye MUST take control precedence over ordinary dictated content. Quoted, mentioned, negated, reported, ambiguous, or non-standalone occurrences MUST remain dictated data and MUST NOT close the conversation.

#### Scenario: Standalone dictation control

- GIVEN dictation mode is active
- WHEN the standalone transcript is `hasta luego`
- THEN the interpreter MUST classify it as goodbye control
- AND MUST NOT append it as dictated content

#### Scenario: Quoted dictation content

- GIVEN dictation mode is active
- WHEN the user dictates content such as `escribí "hasta luego" en la nota`
- THEN the goodbye words MUST remain dictated data
- AND the conversation MUST remain active

## MODIFIED Requirements

### Requirement: Re-ask then reveal (RNF-4)

When the interpreter cannot resolve an utterance with confidence, it MUST re-ask up to 2 times and then reveal the raw transcript for manual correction. It MUST never execute a partial or ambiguous action. Goodbye classification MUST occur before ordinary intent execution, but only an exact standalone approved phrase MAY bypass re-ask handling; all other goodbye-like occurrences MUST fail closed and follow ordinary interpretation or re-ask behavior.
(Previously: Unresolved utterances followed re-ask handling without a deterministic lifecycle-control classification seam.)

#### Scenario: Ambiguous goodbye-like input

- GIVEN an active conversation and a transcript containing an ambiguous or non-standalone goodbye phrase
- WHEN the interpreter evaluates it
- THEN it MUST NOT close the conversation
- AND it MUST either resolve the remaining request or use the existing re-ask flow

#### Scenario: Unknown command remains safe

- GIVEN the transcript is neither an exact approved goodbye nor a resolvable allowlisted command
- WHEN interpretation completes
- THEN no action MUST execute
- AND the existing re-ask or raw-transcript reveal behavior MUST apply
